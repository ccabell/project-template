//
//  AnConsultationViewController+UI.swift
//  A360Scribe
//
//  Created by Mike Grankin on 18.02.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import UIKit
import BezelKit

internal extension AnConsultationViewController {
  
  // MARK: - Actions
  
  @IBAction func onSegmentedControlValueChanged(_ sender: AnSegmentedControl) {
    updateConsoleVisibility()
    guard consultation != nil,
          let currentSegmentDetails = sender.currentSegmentDetails,
          let consultationSelectedTab = AnConsultationTab(displayTitle: currentSegmentDetails.title) else {
      return
    }
    
    handleWebView(selectedTab: consultationSelectedTab)
  }
  
  @IBAction func onCloseAction(_ sender: UIButton) {
    if sessionStatus.isInTransition {
      showAlert("Data processing, please wait.", source: sender)
    } else if sessionStatus.isActiveRecording {
      showActiveConsultationAlert(hasActiveRecording: true)
    } else if sessionStatus != .stopped {
      showActiveConsultationAlert(hasActiveRecording: false)
    } else {
      needsClosing = true
      handleCloseIfNeeded()
    }
  }
  
  @IBAction func onRecordAction(_ sender: Any) {
    toggleAudioStreaming()
  }
  
  @IBAction func onFinishAction(_ sender: Any) {
    toggleConsultationControls(confirmationMode: true)
  }
  
  @IBAction func onDiscardAction(_ sender: Any) {
    toggleConsultationControls(confirmationMode: false)
  }
  
  @IBAction func onConfirmAction(_ sender: Any) {
    toggleConsultationControls(confirmationMode: false)
    needFinish = true
    handleStopOrClose()
  }
  
  @IBAction func onToggleConsoleAction(_ sender: Any) {
    var toggleIconName = ""
    if consoleTextView.isHidden {
      consoleTextView.isHidden = false
      toggleIconName = "chevron.compact.down"
    } else {
      consoleTextView.isHidden = true
      toggleIconName = "chevron.compact.up"
    }
    let toggleIcon = UIImage(systemName: toggleIconName) ?? UIImage()
    toggleConsoleButton.setImage(toggleIcon, for: .normal)
  }
  
  // MARK: - UI
  
  func configureInitialStateUI() {
    if AnUserManager.shared.currentUser?.hideTranscript ?? true {
      segmentedControl.hideSegments(withTitles: ["Transcript"])
    }
#if !(DEBUG)
    segmentedControl.hideSegments(withTitles: ["Intents", "Entities", "Sentiments"])
#endif
    updateConsoleVisibility()
    setNavigationTitle(patient?.displayName, subtitle: patient?.formattedBirthDateWithAge)
    consoleTextView.text = ""
    webView.isHidden = true
    webViewEmptyStateView.isHidden = false
    segmentedControl.isHidden = true
    configureBottomPanelLayout()
  }
  
  func updateStatus(_ status: ConsultationSessionStatus) {
    switch status {
    case .initializing:
      setRecordingButtons(recordEnabled: false, recordImageSystemName: "mic.circle.fill")
      applyProgressIndicator()
      statusLabel.text = "Initializing Consultation"
      
    case .reconnecting(let attemptNumber):
      setRecordingButtons(recordEnabled: false, recordImageSystemName: "mic.circle.fill")
      applyProgressIndicator()
      statusLabel.text = "Reconnecting (\(attemptNumber))..."
      
    case .connected:
      setRecordingButtons(recordEnabled: true, recordImageSystemName: "mic.circle.fill")
      setRecordingStatusImage(systemName: "waveform", tintColor: .secondaryMedium, variableValue: 0.0)
      statusLabel.text = "Start Recording"
      
    case .startingRecording:
      setRecordingButtons(recordEnabled: false)
      applyProgressIndicator()
      statusLabel.text = "Starting Recording"
      
    case .recording:
      setRecordingButtons(recordEnabled: true, recordImageSystemName: "pause.circle.fill")
      setRecordingStatusImage(systemName: "waveform", tintColor: .primarySoft, variableValue: 0.1) {
        if #available(iOS 18.0, *) {
          $0.addSymbolEffect(.variableColor.iterative.hideInactiveLayers, options: .repeat(.continuous))
        } else {
          $0.addSymbolEffect(.variableColor.iterative.hideInactiveLayers, options: .repeating)
        }
      }
      statusLabel.text = "Recording"
      
    case .recordingInterrupted:
      setRecordingButtons(recordEnabled: false, finishEnabled: true)
      setRecordingStatusImage(systemName: "nosign", tintColor: .primarySoft)
      statusLabel.text = "Recording paused by system"
      
    case .finishingRecording:
      setRecordingButtons(recordEnabled: false)
      applyProgressIndicator()
      statusLabel.text = "Stopping Recording"
      
    case .recordingStopped:
      setRecordingButtons(recordEnabled: true, recordImageSystemName: "mic.circle.fill")
      setRecordingStatusImage(systemName: "pause.circle", tintColor: .primarySoft)
      statusLabel.text = "Recording Paused"
      
    case .stoppingConsultation:
      setRecordingButtons(recordEnabled: false, recordImageSystemName: "mic.circle.fill")
      applyProgressIndicator()
      statusLabel.text = "Stopping Consultation"
      
    case .stopped:
      setRecordingStatusImage(systemName: "flag.pattern.checkered.circle", tintColor: .primarySoft)
      statusLabel.text = "Consultation Finished"
      recordButton.isHidden = true
      finishButton.isHidden = true

    case .error(let errorMessage):
      setRecordingButtons(recordEnabled: true, recordImageSystemName: "mic.circle.fill")
      setRecordingStatusImage(systemName: "xmark.circle", tintColor: .primarySoft)
      statusLabel.text = errorMessage
    }
  }
  
  private func updateConsoleVisibility() {
#if DEBUG
    let isRecordingSegmentSelected = segmentedControl.currentSegmentDetails?.title == "Transcript"
    consoleTextView.isHidden = !isRecordingSegmentSelected
    toggleConsoleButton.isHidden = !isRecordingSegmentSelected
#else
    consoleTextView.isHidden = true
    toggleConsoleButton.isHidden = true
#endif
  }
  
  private func setRecordingStatusImage(systemName: String, tintColor: UIColor, variableValue: Double? = nil, effectApplier: ((UIImageView) -> Void)? = nil) {
    statusImageView.removeAllSymbolEffects(animated: false)
    var image: UIImage
    if let variableValue,
       let systemImage = UIImage(systemName: systemName, variableValue: variableValue) {
      image = systemImage
    } else if let systemImage = UIImage(systemName: systemName) {
      image = systemImage
    } else {
      return
    }
    
    statusImageView.image = image.withTintColor(tintColor, renderingMode: .alwaysOriginal)
    effectApplier?(statusImageView)
  }
  
  private func setRecordingButtons(recordEnabled: Bool, recordImageSystemName: String? = nil, finishEnabled: Bool? = nil) {
    recordButton.isEnabled = recordEnabled
    finishButton.isEnabled = finishEnabled ?? recordEnabled
    guard let recordImageSystemName else { return }
    recordButton.image = UIImage(systemName: recordImageSystemName, withConfiguration: UIImage.SymbolConfiguration(scale: .large))
  }
  
  private func applyProgressIndicator() {
    if #available(iOS 18.0, *) {
      setRecordingStatusImage(systemName: "progress.indicator", tintColor: .secondaryMedium) {
        $0.addSymbolEffect(.variableColor.iterative.dimInactiveLayers.nonReversing, options: .repeat(.continuous))
      }
    } else {
      setRecordingStatusImage(systemName: "ellipsis", tintColor: .secondaryMedium) {
        $0.addSymbolEffect(.variableColor.iterative.dimInactiveLayers.nonReversing, options: .repeating)
      }
    }
  }
  
  private func configureBottomPanelLayout() {
    let minInset: CGFloat = 20.0
    let fixedRadius = recordingView.cornerRadius
    let screenRadius = CGFloat.deviceBezel
    let requiredGap = max(minInset, screenRadius - fixedRadius)

    recordingViewLeftInsetConstraint.constant = requiredGap
    recordingViewRightInsetConstraint.constant = requiredGap
    recordingViewBottomInsetConstraint.constant = requiredGap
    statusImageViewRightInsetConstraint.constant = fixedRadius - statusImageView.width / 2.0
  }
  
  private func showActiveConsultationAlert(hasActiveRecording: Bool) {
    let alertTitle = hasActiveRecording ? "Recording in Progress" : "Consultation in Progress"
    let alertMessage = hasActiveRecording ? "Existing will pause the recording and make the consultation idle. You will be able to resume it." : "Existing will make the consultation idle. You will be able to resume it."
    let idleActionTitle = hasActiveRecording ? "Pause Recording & Exit" : "Exit"
    var preferredStyle =  UIAlertController.Style.alert
    var cancelStyle = UIAlertAction.Style.cancel
    if #available(iOS 26.0, *) {
      preferredStyle = .actionSheet
      cancelStyle = .default
    }
    let alert = UIAlertController(title: alertTitle, message: alertMessage, preferredStyle: preferredStyle)
    alert.addAction(UIAlertAction(title: idleActionTitle, style: .default) { [weak self] _ in
      self?.needsClosing = true
      self?.needFinish = false
      self?.handleStopOrClose()
    })
    alert.addAction(UIAlertAction(title: "Finish Consultation & Exit", style: .default) { [weak self] _ in
      self?.needsClosing = true
      self?.needFinish = true
      self?.handleStopOrClose()
    })
    alert.addAction(UIAlertAction(title: "Stay in Consultation", style: cancelStyle))
    alert.popoverPresentationController?.sourceItem = closeButton
    showAlert(alert)
  }
  
  private func toggleConsultationControls(confirmationMode: Bool) {
    recordButton.isHidden = confirmationMode
    finishButton.isHidden = confirmationMode
    confirmButton.isHidden = !confirmationMode
    discardButton.isHidden = !confirmationMode
  }
  
  // MARK: - Helpers
  
  func handleMessage(_ message: String, color: UIColor = .black) {
    Task { @MainActor in
      let messageText = makeTimestampedMessage(from: message, color: color)
      let existingText = NSMutableAttributedString(attributedString: consoleTextView.attributedText)
      existingText.append(messageText)
      consoleTextView.attributedText = existingText
      let textCount = consoleTextView.attributedText.length
      if textCount >= 1 {
        consoleTextView.scrollRangeToVisible(NSRange(location: textCount - 1, length: 1))
      }
    }
  }
  
  private func makeTimestampedMessage(from message: String, color: UIColor = .black) -> NSAttributedString {
    let dateFormatter = DateFormatter()
    dateFormatter.dateFormat = "HH:mm:ss.SSS"
    let timestamp = dateFormatter.string(from: Date())
    let fullText = "[\(timestamp)] \(message)\n"
    return NSAttributedString(string: fullText, attributes: [.foregroundColor: color])
  }
}
