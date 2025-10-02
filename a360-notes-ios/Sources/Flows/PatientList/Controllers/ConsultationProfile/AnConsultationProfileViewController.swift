//
//  AnConsultationProfileViewController.swift
//  A360Scribe
//
//  Created by Mike Grankin on 28.04.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import UIKit
import WebKit

protocol AnConsultationProfileOutput {
  var onResumeConsultation: ((AnPatient, AnConsultation) -> Void)? { get set }
  var onClose: ((AnConsultation?) -> Void)? { get set }
  var patient: AnPatient? { get set }
  var consultation: AnConsultation? { get set }
}

final class AnConsultationProfileViewController: AnBaseViewController, AnConsultationProfileOutput {
  
  // MARK: - Output
  
  var onResumeConsultation: ((AnPatient, AnConsultation) -> Void)?
  var onClose: ((AnConsultation?) -> Void)?
  var patient: AnPatient?
  var consultation: AnConsultation?
  
  // MARK: - Outlets
  
  @IBOutlet private weak var finishConsultationBarButtonItem: UIBarButtonItem!
  @IBOutlet private weak var resumeConsultationBarButtonItem: UIBarButtonItem!
  @IBOutlet private weak var webView: WKWebView!
  
  // MARK: - Private Properties
  
  private var isConsultationUpdated: Bool = false
  private lazy var consultationService: AnConsultationService = AnAPIService()
  private lazy var webViewService = AnWebViewService()
  private lazy var webViewBridge = AnConsultationProfileWebViewBridge(webView: webView)
  
  // MARK: - Lifecycle
  
  override func viewDidLoad() {
    super.viewDidLoad()
    configureUI()
    configureWebView()
    setupAppStateObservers()
  }
  
  deinit {
    NotificationCenter.default.removeObserver(self)
  }
  
  // MARK: - Actions
  
  @IBAction private func onFinishAction(_ sender: Any) {
    Task {
      defer {
        hideHUD()
      }
      
      do {
        showHUD()
        finishConsultationBarButtonItem.isEnabled = false
        guard let consultationId = consultation?.id else { return }
        
        let updatedConsultation = try await consultationService.update(consultationId: consultationId, status: .finished)
        refresh(consultation: updatedConsultation)
      } catch {
        finishConsultationBarButtonItem.isEnabled = true
        showErrorBanner(error.localizedDescription)
      }
    }
  }
  
  @IBAction private func onResumeConsultationAction(_ sender: Any) {
    guard let patient, let consultation else { return }
    onResumeConsultation?(patient, consultation)
  }
  
  @IBAction private func onBackAction(_ sender: Any) {
    onClose?(isConsultationUpdated ? consultation : nil)
  }
  
  // MARK: - Public Functions
  
  func refresh(consultation updatedConsultation: AnConsultation?) {
    if let updatedConsultation {
      isConsultationUpdated = true
      consultation = updatedConsultation
    }
    configureUI()
    configureWebView()
  }
  
  // MARK: - Private Functions
  
  private func configureUI() {
    setNavigationTitle(patient?.displayName, subtitle: patient?.formattedBirthDateWithAge)
  }
  
  private func updateBarButtons(enabled: Bool, hidden: Bool) {
    finishConsultationBarButtonItem.isEnabled = enabled
    resumeConsultationBarButtonItem.isEnabled = enabled
    finishConsultationBarButtonItem.isHidden = hidden
    resumeConsultationBarButtonItem.isHidden = hidden
  }
  
  private func configureWebView() {
    updateBarButtons(enabled: false, hidden: consultation?.prohibitedActionMessage != nil)
    guard let patient, let consultationId = consultation?.id else { return }
    Task { @MainActor in
      webView.navigationDelegate = self
      let url = webViewService.generateURL(for: .consultationProfile(patientId: patient.id, consultationId: consultationId))
      await webView.configuration.websiteDataStore.removeData(ofTypes: WKWebsiteDataStore.allWebsiteDataTypes(), modifiedSince: .distantPast)
      showHUD()
      webView.load(URLRequest(url: url))
    }
    webViewBridge.onEvent = { [weak self] event in
      self?.handleWebViewEvent(event)
    }
    webViewBridge.onError = { [weak self] error in
      self?.showErrorBanner(error.localizedDescription)
    }
  }
  
  private func setupAppStateObservers() {
    NotificationCenter.default.addObserver(self, selector: #selector(appDidEnterBackground), name: UIApplication.didEnterBackgroundNotification, object: nil)
    NotificationCenter.default.addObserver(self, selector: #selector(appDidBecomeActive), name: UIApplication.didBecomeActiveNotification, object: nil)
  }
  
  @objc
  private func appDidEnterBackground() {
    webViewBridge.send(name: AnConsultationProfileWebViewBridge.appDidEnterBackgroundEventName)
  }
  
  @objc
  private func appDidBecomeActive() {
    webViewBridge.send(name: AnConsultationProfileWebViewBridge.appDidBecomeActiveEventName)
  }
  
  private func handleWebViewEvent(_ event: AnConsultationProfileWebViewBridge.WebEvent) {
    switch event {
    case .openUnsavedFeedbackChangesAlert:
      showAlert("You haven’t sent your comments. Discard them or stay to send feedback?",
                title: "Unsaved Comments",
                proceedTitle: "Discard",
                proceedStyle: .destructive,
                cancelTitle: "Stay") { [weak self] in
        self?.webViewBridge.send(name: AnConsultationProfileWebViewBridge.closeFeedbackModalEventName)
      }
    case .contentDidLoad:
      updateBarButtons(enabled: true, hidden: consultation?.prohibitedActionMessage != nil)
    }
  }
}

// MARK: - WKNavigationDelegate

extension AnConsultationProfileViewController: WKNavigationDelegate {
  func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
    hideHUD()
  }
  
  func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
    hideHUD()
    showErrorBanner(error.localizedDescription)
    updateBarButtons(enabled: false, hidden: consultation?.prohibitedActionMessage != nil)
  }
  
  func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
    hideHUD()
    showErrorBanner(error.localizedDescription)
    updateBarButtons(enabled: false, hidden: consultation?.prohibitedActionMessage != nil)
  }
}
