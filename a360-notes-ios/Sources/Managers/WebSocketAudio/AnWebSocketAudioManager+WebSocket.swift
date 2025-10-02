//
//  AnWebSocketAudioManager+WebSocket.swift
//  A360Scribe
//
//  Created by Mike Grankin on 14.05.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import AVFoundation

internal extension AnWebSocketAudioManager {
  
  // MARK: - WebSocket
  
  func initConsultationWebSocket() {
    Task {
      do {
        if consultation == nil {
          consultation = try await consultationService.initiate(patient: patient)
        }
        setupWebSocket()
      } catch {
        onError?(error.localizedDescription)
      }
    }
  }
  
  func setupWebSocket() {
    guard let webSocketUrl = URL(string: GlobalLinks.webSocketUrl) else { return }
    webSocketTask?.cancel(with: .goingAway, reason: nil)
    
    let request = URLRequest(url: webSocketUrl)
    webSocketTask = URLSession.shared.webSocketTask(with: request)
    webSocketTask?.resume()
    shouldStopReceivingMessages = false
    listenForMessages()
  }
  
  private func handleConnectedStatus() async throws {
    try await authorizeWebSocket()
  }
  
  private func handleAuthenticatedStatus() async throws {
    guard let consultation else { return }
    try await attachSessionWebSocket(consultation: consultation)
  }
  
  private func authorizeWebSocket() async throws {
    let authHeader = try await AnSessionManager.shared.getValidAuthHeader()
    try await sendWebSocketMessage(.authorize(token: authHeader))
  }
  
  private func attachSessionWebSocket(consultation: AnConsultation) async throws {
    guard let expertId = AnUserManager.shared.currentUser?.expertId,
          let practiceId = AnUserManager.shared.currentUser?.practiceId else {
      throw WebSocketError.invalidPayload
    }
    try await sendWebSocketMessage(.attachSession(consultationId: consultation.id,
                                                  patientId: consultation.patient.id,
                                                  expertId: expertId,
                                                  practiceId: practiceId))
  }
  
  func startAudioStream() {
    guard let recordingFormat, let bitDepth = recordingFormat.settings[AVLinearPCMBitDepthKey] as? Int
    else { return }
    sequenceNumber = 0
    Task {
      do {
        try await sendWebSocketMessage(.sessionStart(rate: recordingFormat.sampleRate, bitDepth: bitDepth, channels: recordingFormat.channelCount))
        startRecording()
      } catch {
        onError?("Unable to establish live connection: \(error.localizedDescription)")
      }
    }
  }
  
  func stopAudioStream() {
    Task {
      do {
        try await sendWebSocketMessage(.sessionEnd(sequence: sequenceNumber))
      } catch {
        onError?("Unable to close live connection: \(error.localizedDescription)")
      }
    }
  }
  
  func initiateStopingWebSocket(shouldFinishConsultation: Bool) {
    shouldStopReceivingMessages = true
    Task {
      do {
        try await updateConsultationStatus(to: shouldFinishConsultation ? .finished : .idle)
        webSocketTask?.cancel(with: .normalClosure, reason: nil)
        onStopped?(consultation)
      } catch {
        onError?("Unable to stop live connection: \(error.localizedDescription)")
      }
    }
  }
  
  private func updateConsultationStatus(to status: AnConsultationStatus) async throws {
    guard let consultationId = consultation?.id else { return }
    consultation = try await consultationService.update(consultationId: consultationId, status: status)
  }
  
  private func sendWebSocketMessage(_ message: AnWebSocketMessage) async throws {
    let jsonData: Data
    do {
      jsonData = try message.payload.jsonData()
    } catch {
      throw WebSocketError.invalidPayload
    }
    
    guard let webSocketTask else {
      throw WebSocketError.taskUnavailable
    }
    
    do {
      try await webSocketTask.send(.data(jsonData))
    } catch {
      try processSocketError(error)
    }
  }
  
  func sendAudioData(_ audioData: Data?) {
    guard let audioData else { return }
    onMessage?("sendAudioData")
    Task {
      do {
        try await sendWebSocketMessage(.audioChunk(data: audioData, sequence: sequenceNumber))
      } catch {
        switch error {
        case WebSocketError.networkUnavailable:
          handleAudioSessionInterruption(type: .began)
          wasAudioPausedDueToNetwork = true
          return
        default:
          break
        }
        onError?("Unable to send audio data: \(error.localizedDescription)")
      }
    }
    
    sequenceNumber += 1
    AnSessionTimeoutManager.shared.updateTimer()
  }
  
  private func listenForMessages() {
    Task {
      guard let webSocketTask else { return }
      
      do {
        let result = try await webSocketTask.receive()
        
#if DEBUG
        let messageText: String
        switch result {
        case .string(let text): messageText = text
        case .data(let data): messageText = String(data: data, encoding: .utf8) ?? ""
        @unknown default: messageText = ""
        }
        onMessage?("Received: \(messageText)")
#endif
        
        switch result {
        case .string(let text):
          if let textData = text.data(using: .utf8) {
            try await tryHandleMessage(textData)
          }
          
        case .data(let data):
          try await tryHandleMessage(data)
          
        @unknown default:
          break
        }
        listenForMessages()
      } catch {
        guard !shouldStopReceivingMessages else { return }
        onError?("Live connection error: \(error.localizedDescription)")
        try? processSocketError(error)
      }
    }
  }
  
  private func tryHandleMessage(_ data: Data) async throws {
    if (try? JSONDecoder().decode(AnWebSocketSummaryResponse.self, from: data)) != nil {
      onRecordingStopped?()
      return
    }
    if let statusResponse = try? JSONDecoder().decode(AnWebSocketStatusResponse.self, from: data) {
      try await handleWebSocketStatus(statusResponse)
      return
    }
    
    if let eventResponse = try? JSONDecoder().decode(AnWebSocketEventResponse.self, from: data) {
      try await handleWebSocketEvent(eventResponse.event)
      return
    }
    
    throw WebSocketError.unknownMessageFormat(data)
  }
  
  private func handleWebSocketStatus(_ statusResponse: AnWebSocketStatusResponse) async throws {
    switch statusResponse.status {
    case .error:
      if let error = statusResponse.error {
        throw WebSocketError.receivedServerError(error)
      }
      
    case .connected:
      try await handleConnectedStatus()
      
    case .authenticated:
      try await handleAuthenticatedStatus()
      
    case .attached:
      if let consultation {
        onInitCompleted?(consultation)
      }
      retryCount = 0
      if wasAudioPausedDueToNetwork {
        wasAudioPausedDueToNetwork = false
        handleAudioSessionInterruption(type: .ended)
      }
      
    default:
      onMessage?("WebSocket status: \(statusResponse.status.rawValue)")
    }
  }
  
  private func handleWebSocketEvent(_ event: AnWebSocketEvent) async throws {
    onMessage?("WebSocket event: \(event.rawValue)")
  }
  
  private func processSocketError(_ error: Error) throws {
    if let wsError = error as? WebSocketError, case .networkUnavailable = wsError {
      onMessage?("wsError: \(wsError)")
      handleWebSocketFailure()
      throw wsError
    }
    
    if let posix = error as? POSIXError {
      switch posix.code {
      case .ENOTCONN, .ETIMEDOUT, .ECONNRESET:
        onMessage?("posixError: \(posix.localizedDescription)")
        handleWebSocketFailure()
        throw WebSocketError.networkUnavailable(URLError(.notConnectedToInternet))
      default:
        break
      }
    }
    
    if let urlError = error as? URLError {
      onMessage?("urlError: \(urlError)")
      switch urlError.code {
      case .notConnectedToInternet, .timedOut, .networkConnectionLost, .cannotFindHost, .cannotConnectToHost, .dnsLookupFailed:
        handleWebSocketFailure()
        throw WebSocketError.networkUnavailable(urlError)
      default:
        throw WebSocketError.sendFailed(urlError)
      }
    }
    onMessage?("error: \(error)")
    throw WebSocketError.sendFailed(error)
  }
  
  private func handleWebSocketFailure() {
    stopRecording()
    
    guard retryCount < 10 else {
      onError?("Unable to reconnect after 10 attempts. Please check your internet connection and try again.")
      return
    }
    
    shouldStopReceivingMessages = false
    startRetryingWebSocketConnection()
  }
  
  private func startRetryingWebSocketConnection() {
    guard !isRetrying else { return }
    isRetrying = true
    
    let maxRetryCount = 10
    let maxRetryDuration: TimeInterval = 300.0
    let retryStartTime = Date()
    
    Task {
      defer {
        isRetrying = false
      }
      
      while !shouldStopReceivingMessages,
            webSocketTask?.state != .running,
            retryCount < maxRetryCount,
            Date().timeIntervalSince(retryStartTime) <= maxRetryDuration {
        
        retryCount += 1
        onReconnectAttempt?(retryCount)
        
        let exponentialBackoff = min(baseBackoff * pow(2.0, Double(retryCount)), maxBackoff)
        let jitter = Double.random(in: 0.5 ... 1.0)
        let sleepDuration = exponentialBackoff * jitter
        
        try? await Task.sleep(for: .seconds(sleepDuration))
        
        guard !shouldStopReceivingMessages else { break }
        
        setupWebSocket()
      }
      
      if retryCount >= maxRetryCount {
        onError?("Unable to reconnect after \(retryCount) attempts. Please check your internet connection and try again.")
      } else if Date().timeIntervalSince(retryStartTime) > maxRetryDuration {
        onError?("Unable to reconnect after several minutes. Please check your connection and try again.")
      }
    }
  }
  
  // MARK: - Enums
  
  private enum WebSocketError: Error {
    case invalidPayload
    case taskUnavailable
    case sendFailed(Error)
    case networkUnavailable(URLError)
    case receivedServerError(String)
    case unknownMessageFormat(Data)
    
    var localizedDescription: String {
      switch self {
      case .invalidPayload:
        return "Data processing error."
      case .taskUnavailable:
        return "Live connection failed."
      case .sendFailed(let error):
        return error.localizedDescription
      case .networkUnavailable(let urlError):
        return "Network unavailable: \(urlError.localizedDescription)."
      case .receivedServerError(let message):
        return "Server error: \(message)."
      case .unknownMessageFormat:
        return "Data processing error."
      }
    }
  }
  
  private enum AnWebSocketMessage {
    case authorize(token: String)
    case attachSession(consultationId: String, patientId: String, expertId: String, practiceId: String)
    case sessionStart(rate: Double, bitDepth: Int, channels: AVAudioChannelCount)
    case sessionEnd(sequence: Int)
    case audioChunk(data: Data, sequence: Int)
    
    var payload: [String: Any?] {
      switch self {
      case .authorize(let token):
        return ["message": "authorization", "token": token]
      case .attachSession(let consultationId, let patientId, let expertId, let practiceId):
        return ["message": "attach-session", "consultation_id": consultationId, "patient_id": patientId, "expert_id": expertId, "practice_id": practiceId]
      case .sessionStart(let rate, let bitDepth, let channels):
        return ["message": "session-start", "sample-rate": rate, "bit-depth": bitDepth, "channels": channels]
      case .sessionEnd(let sequence):
        return ["message": "session-end", "sequenceCount": sequence]
      case .audioChunk(let data, let sequence):
        return ["message": "audio-chunk", "payload": data.base64EncodedString(), "sequenceNumber": sequence]
      }
    }
  }
}
