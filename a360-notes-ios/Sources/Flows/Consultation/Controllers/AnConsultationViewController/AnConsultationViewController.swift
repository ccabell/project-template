//
//  AnConsultationViewController.swift
//  A360Scribe
//
//  Created by Mike Grankin on 29.01.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import UIKit
import AVFoundation
import WebKit

protocol AnConsultationOutput: AnyObject {
  var finishFlow: ((AnConsultation?) -> Void)? { get set }
  var patient: AnPatient? { get set }
  var consultation: AnConsultation? { get set }
}

final class AnConsultationViewController: AnBaseViewController, AnConsultationOutput {
  
  // MARK: - Output
  
  var finishFlow: ((AnConsultation?) -> Void)?
  var patient: AnPatient?
  var consultation: AnConsultation?
  
  // MARK: - Outlets
  
  @IBOutlet internal weak var closeButton: UIBarButtonItem!
  @IBOutlet internal weak var recordButton: UIBarButtonItem!
  @IBOutlet internal weak var finishButton: UIBarButtonItem!
  @IBOutlet internal weak var confirmButton: UIBarButtonItem!
  @IBOutlet internal weak var discardButton: UIBarButtonItem!
  @IBOutlet internal weak var segmentedControl: AnSegmentedControl!
  @IBOutlet internal weak var voiceAssistView: UIView!
  @IBOutlet internal weak var recordingView: UIView!
  @IBOutlet internal weak var statusImageView: UIImageView!
  @IBOutlet internal weak var statusLabel: UILabel!
  @IBOutlet internal weak var toggleConsoleButton: UIButton!
  @IBOutlet internal weak var consoleTextView: UITextView!
  @IBOutlet internal weak var webViewEmptyStateView: AnEmptyStateView!
  @IBOutlet internal weak var webView: WKWebView!
  @IBOutlet internal weak var recordingViewLeftInsetConstraint: NSLayoutConstraint!
  @IBOutlet internal weak var recordingViewRightInsetConstraint: NSLayoutConstraint!
  @IBOutlet internal weak var recordingViewBottomInsetConstraint: NSLayoutConstraint!
  @IBOutlet internal weak var statusImageViewRightInsetConstraint: NSLayoutConstraint!
  
  // MARK: - Private Properties
  
  internal var webSocketAudioManager: AnWebSocketAudioManager?
  internal var needsClosing: Bool = false
  internal var needFinish: Bool = false
  internal var sessionStatus: ConsultationSessionStatus = .initializing {
    didSet {
      Task { @MainActor in
        updateStatus(sessionStatus)
      }
    }
  }
  internal var isAutoScrollEnabled = true
  internal let bottomScrollThreshold: CGFloat = 20.0
  private lazy var webViewService = AnWebViewService()
  private lazy var consultationWebViewBridge = AnConsultationWebViewBridge(webView: webView)
  
  // MARK: - Enums
  
  internal enum ConsultationSessionStatus: Equatable {
    case initializing
    case reconnecting(Int)
    case connected
    case startingRecording
    case recording
    case recordingInterrupted
    case finishingRecording
    case recordingStopped
    case stoppingConsultation
    case stopped
    case error(String)
    
    var isActiveRecording: Bool {
      return [.startingRecording, .recording, .recordingInterrupted].contains(self)
    }

    var isInTransition: Bool {
      switch self {
      case .initializing, .reconnecting, .startingRecording, .finishingRecording, .stoppingConsultation:
        return true
      default:
        return false
      }
    }

    static func == (lhs: ConsultationSessionStatus, rhs: ConsultationSessionStatus) -> Bool {
      switch (lhs, rhs) {
      case (.initializing, .initializing),
        (.reconnecting, .reconnecting),
        (.connected, .connected),
        (.startingRecording, .startingRecording),
        (.recording, .recording),
        (.recordingInterrupted, .recordingInterrupted),
        (.finishingRecording, .finishingRecording),
        (.recordingStopped, .recordingStopped),
        (.stoppingConsultation, .stoppingConsultation),
        (.stopped, .stopped),
        (.error, .error):
        return true
      default:
        return false
      }
    }
  }
  
  // MARK: - Lifecycle
  
  override func viewDidLoad() {
    super.viewDidLoad()
    checkMicrophoneAccess()
    configureInitialStateUI()
    configureTimeoutManager()
    initWebSocketAudioManager()
    handleDeviceSleepMode(preventSleep: true)
  }
  
  deinit {
    handleDeviceSleepMode(preventSleep: false)
  }
  
  // MARK: - Private functions
  
  private func configureTimeoutManager() {
    NotificationCenter.default.addObserver(self, selector: #selector(performLogout), name: GlobalConstants.Notifications.performLogout.name, object: nil)
  }
  
  private func checkMicrophoneAccess() {
    switch AVAudioApplication.shared.recordPermission {
    case .granted:
      break
    case .undetermined:
      AVAudioApplication.requestRecordPermission { [weak self] granted in
        guard !granted else { return }
        print(#function, "Not Granted")
        self?.showMicrophoneAccessAlert()
      }
    case .denied:
      showMicrophoneAccessAlert()
    @unknown default:
      break
    }
  }
  
  private func initWebSocketAudioManager() {
    guard let patient else {
      showErrorBanner("Missing patient. Please restart consultation.")
      return
    }
    
    sessionStatus = .initializing
    webSocketAudioManager = AnWebSocketAudioManager(patient: patient, consultation: consultation)
    webSocketAudioManager?.onInitCompleted = { [weak self] consultation in
      guard let self else { return }
      let resumingConsultation = self.consultation != nil
      sessionStatus = .connected
      self.consultation = consultation
      configureWebView(resumingConsultation: resumingConsultation)
      toggleAudioStreaming()
    }
    webSocketAudioManager?.onRecordStarted = { [weak self] in
      self?.sessionStatus = .recording
    }
    webSocketAudioManager?.onRecordInterrupted = { [weak self] in
      self?.sessionStatus = .recordingInterrupted
    }
    webSocketAudioManager?.onRecordResumed = { [weak self] in
      self?.sessionStatus = .recording
    }
    webSocketAudioManager?.onMessage = { [weak self] message in
      AnSessionTimeoutManager.shared.updateTimer()
      print(message)
#if DEBUG
      self?.handleMessage(message)
#endif
    }
    webSocketAudioManager?.onError = { [weak self] errorMessage in
      self?.sessionStatus = .error(errorMessage)
#if DEBUG
      self?.handleMessage(errorMessage, color: .red)
#endif
    }
    webSocketAudioManager?.onRecordingStopped = { [weak self] in
      self?.sessionStatus = .recordingStopped
      self?.handleCloseIfNeeded()
    }
    
    webSocketAudioManager?.onStopped = { [weak self] consultation in
      self?.consultation = consultation
      self?.sessionStatus = .stopped
      self?.needFinish = false
      self?.handleCloseIfNeeded()
    }
    
    webSocketAudioManager?.onReconnectAttempt = { [weak self] attemptNumber in
      self?.sessionStatus = .reconnecting(attemptNumber)
    }
  }
  
  internal func toggleAudioStreaming() {
    let isWebSocketAudioManagerActive = webSocketAudioManager?.isRecording
    if !(isWebSocketAudioManagerActive ?? false) {
      sessionStatus = .startingRecording
      webSocketAudioManager?.startRecordingAndStreaming()
    } else {
      stopRecording()
    }
  }
  
  private func stopRecording() {
    sessionStatus = .finishingRecording
    webSocketAudioManager?.stopRecordingAndStreaming()
  }
  
  internal func handleStopOrClose() {
    if sessionStatus.isActiveRecording {
      stopRecording()
    } else {
      closeConnection()
    }
  }
  
  internal func handleCloseIfNeeded() {
    guard needsClosing || needFinish else { return }
    Task {
      if sessionStatus != .stopped {
        closeConnection()
      } else {
        needsClosing = false
        finishFlow?(consultation)
      }
    }
  }
  
  private func closeConnection() {
    sessionStatus = .stoppingConsultation
    webSocketAudioManager?.closeConnection(shouldFinishConsultation: needFinish)
  }
  
  @objc
  private func performLogout(_: NSNotification) {
    needsClosing = true
    handleCloseIfNeeded()
  }
  
  private func handleDeviceSleepMode(preventSleep: Bool) {
    UIApplication.shared.isIdleTimerDisabled = preventSleep
  }
  
  private func configureWebView(resumingConsultation: Bool) {
    guard let consultation, let patient else { return }
    Task { @MainActor in
      webView.navigationDelegate = self
      let url = webViewService.generateURL(for: .consultationSession(patientId: patient.id,
                                                                     consultationId: consultation.id,
                                                                     activeTab: AnConsultationTab.summaryAI.rawValue,
                                                                     resumingConsultation: resumingConsultation))
      await webView.configuration.websiteDataStore.removeData(ofTypes: WKWebsiteDataStore.allWebsiteDataTypes(), modifiedSince: .distantPast)
      webView.load(URLRequest(url: url))
    }
    
    consultationWebViewBridge.onError = { [weak self] error in
      self?.showErrorBanner(error.localizedDescription)
    }
    consultationWebViewBridge.onEvent = { [weak self] event in
      self?.handleWebViewEvent(event)
    }
  }
  
  internal func handleWebView(selectedTab: AnConsultationTab) {
    let event = AnConsultationWebViewBridge.SetActiveTabEvent(payload: .init(activeTab: selectedTab.rawValue))
    consultationWebViewBridge.send(event)
  }
  
  private func handleWebViewEvent(_ event: AnConsultationWebViewBridge.WebEvent) {
    switch event {
    case .updateTabContent(let tab):
      segmentedControl.animateSegment(withTitle: tab.displayTitle)
    }
  }
}

// MARK: - WKNavigationDelegate

extension AnConsultationViewController: WKNavigationDelegate {
  func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
    showWebContentUI()
  }
  
  func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
    showWebContentUI()
    showErrorBanner(error.localizedDescription)
  }
  
  func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
    showWebContentUI()
    showErrorBanner(error.localizedDescription)
  }
  
  private func showWebContentUI() {
    webViewEmptyStateView.isHidden = true
    webView.isHidden = false
    segmentedControl.isHidden = false
  }
}
