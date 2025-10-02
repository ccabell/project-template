//
//  AnWebSocketAudioManager.swift
//  A360Scribe
//
//  Created by Mike Grankin on 10.02.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import AVFoundation
import UIKit

protocol AnWebSocketAudioManagerOutput {
  var onReconnectAttempt: ((Int) -> Void)? { get set }
  var onInitCompleted: ((AnConsultation) -> Void)? { get set }
  var onRecordStarted: (() -> Void)? { get set }
  var onRecordInterrupted: (() -> Void)? { get set }
  var onRecordResumed: (() -> Void)? { get set }
  var onMessage: ((_ message: String) -> Void)? { get set }
  var onRecordingStopped: (() -> Void)? { get set }
  var onStopped: ((AnConsultation?) -> Void)? { get set }
  var onError: ((_ message: String) -> Void)? { get set }
}

final class AnWebSocketAudioManager: NSObject, AVAudioRecorderDelegate, AnWebSocketAudioManagerOutput {
  
  // MARK: - Output
  
  var onReconnectAttempt: ((Int) -> Void)?
  var onInitCompleted: ((AnConsultation) -> Void)?
  var onRecordStarted: (() -> Void)?
  var onRecordInterrupted: (() -> Void)?
  var onRecordResumed: (() -> Void)?
  var onMessage: ((_ message: String) -> Void)?
  var onRecordingStopped: (() -> Void)?
  var onStopped: ((AnConsultation?) -> Void)?
  var onError: ((_ message: String) -> Void)?
  
  // MARK: - Public Properties
  
  var isRecording: Bool {
    let isRunning = audioEngine.isRunning
    let isRecording = isRunning && !shouldStopReceivingMessages
    return isRecording
  }
  
  // MARK: - Private Properties
  
  internal var patient: AnPatient
  internal lazy var consultationService: AnConsultationService = AnAPIService()
  internal var webSocketTask: URLSessionWebSocketTask?
  internal var shouldStopReceivingMessages = true
  
  private var audioEngine = AVAudioEngine()
  internal lazy var recordingFormat: AVAudioFormat? = {
    return AVAudioFormat(commonFormat: .pcmFormatInt16, sampleRate: 48000.0, channels: 1, interleaved: true)
  }()
  
  internal var consultation: AnConsultation?
  internal var sequenceNumber: Int = 0
  
  internal var isRetrying = false
  internal var retryCount: Int = 0
  internal let baseBackoff: TimeInterval = 1.0
  internal let maxBackoff: TimeInterval = 60.0
  internal var wasAudioPausedDueToNetwork = false
  
  // MARK: - Lifecycle
  
  init(patient: AnPatient, consultation: AnConsultation?) {
    print("\(type(of: self)) init")
    self.patient = patient
    self.consultation = consultation
    super.init()
    initConsultationWebSocket()
    setupAppStateObservers()
    setupInterruptionObserver()
  }
  
  deinit {
    print("\(type(of: self)) deinit")
    NotificationCenter.default.removeObserver(self)
  }
  
  // MARK: - Public Functions
  
  func startRecordingAndStreaming() {
    do {
      try startAudioSession()
    } catch {
      onError?("Audio streaming session setup failed: \(error.localizedDescription)")
      return
    }
    startAudioStream()
  }
  
  func stopRecordingAndStreaming() {
    stopRecording()
    stopAudioStream()
    stopAudioSession()
  }
  
  func closeConnection(shouldFinishConsultation: Bool = false) {
    initiateStopingWebSocket(shouldFinishConsultation: shouldFinishConsultation)
  }
  
  // MARK: - Private Functions
  
  private func setupAppStateObservers() {
    NotificationCenter.default.addObserver(self, selector: #selector(appDidEnterBackground), name: UIApplication.didEnterBackgroundNotification, object: nil)
    NotificationCenter.default.addObserver(self, selector: #selector(appDidBecomeActive), name: UIApplication.didBecomeActiveNotification, object: nil)
  }
  
  @objc
  private func appDidEnterBackground() {
    guard isRecording else { return }
    AnNotificationManager.shared.scheduleRecordingReminder()
  }
  
  @objc
  private func appDidBecomeActive() {
    AnNotificationManager.shared.clearRecordingReminder()
    
    guard webSocketTask?.state != .suspended else {
      onMessage?("Resuming suspended WebSocket task")
      webSocketTask?.resume()
      return
    }
    
    guard webSocketTask?.state != .running,
          consultation?.status != .finished,
          !shouldStopReceivingMessages else { return }
    
    onReconnectAttempt?(retryCount + 1)
    setupWebSocket()
  }
  
  private func setupInterruptionObserver() {
    NotificationCenter.default.addObserver(self,
                                           selector: #selector(handleAudioSessionInterruption(_:)),
                                           name: AVAudioSession.interruptionNotification,
                                           object: AVAudioSession.sharedInstance())
  }
  
  @objc
  private func handleAudioSessionInterruption(_ notification: Notification) {
    guard let raw = notification.userInfo?[AVAudioSessionInterruptionTypeKey] as? UInt,
          let type = AVAudioSession.InterruptionType(rawValue: raw) else { return }
    handleAudioSessionInterruption(type: type)
  }
  
  internal func handleAudioSessionInterruption(type: AVAudioSession.InterruptionType) {
    switch type {
    case .began:
      audioEngine.pause()
      onRecordInterrupted?()
    case .ended:
      do {
        try AVAudioSession.sharedInstance().setActive(true)
        try audioEngine.start()
        onRecordResumed?()
      } catch {
        onError?("Unable to restore audio streaming session: \(error.localizedDescription)")
      }
    @unknown default:
      break
    }
  }
  
  // MARK: - AudioEngine
  
  private func startAudioSession() throws {
    let session = AVAudioSession.sharedInstance()
    try session.setCategory(.playAndRecord, options: [.defaultToSpeaker, .allowBluetoothHFP])
    try session.setMode(.spokenAudio)
    try session.setActive(true)
  }
  
  private func stopAudioSession() {
    try? AVAudioSession.sharedInstance().setActive(false)
  }
  
  internal func startRecording() {
    guard let recordingFormat, !audioEngine.isRunning else { return }
    
    let inputNode = audioEngine.inputNode
    inputNode.removeTap(onBus: 0)
    
    inputNode.installTap(onBus: 0, bufferSize: 32000, format: recordingFormat) { [weak self] buffer, _ in
      guard let self else { return }
      sendAudioData(bufferToData(buffer))
    }
    
    audioEngine.prepare()
    
    do {
      try audioEngine.start()
      onRecordStarted?()
    } catch {
      onError?("Failed to start audio streaming: \(error.localizedDescription)")
    }
  }
  
  internal func stopRecording() {
    audioEngine.stop()
    audioEngine.inputNode.removeTap(onBus: 0)
  }
  
  // MARK: - Helpers
  
  private func bufferToData(_ buffer: AVAudioPCMBuffer) -> Data? {
    guard let int16ChannelData = buffer.int16ChannelData?[0] else { return nil }
    let audioData = Data(bytes: int16ChannelData, count: Int(buffer.frameLength) * MemoryLayout<Int16>.size)
    return audioData
  }
}
