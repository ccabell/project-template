//
//  UIResponder+Extensions.swift
//  A360Scribe
//
//  Created by Mike Grankin on 24.02.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import UIKit
import SafariServices

extension UIResponder {
  
  // MARK: - Alerts
  
  func showAlert(_ alert: UIAlertController, completion: (() -> Void)? = nil) {
    Task {
      dismissPreviousAlert {
        Task {
          UIApplication.topViewController?.present(alert, animated: true, completion: completion)
        }
      }
    }
  }
  
  func showAlert(_ message: String?, title: String? = nil, proceedTitle: String? = "OK", proceedStyle: UIAlertAction.Style = .default, cancelTitle: String? = nil, source: UIPopoverPresentationControllerSourceItem? = nil, firstResponderAfterProceed: UIResponder? = nil, completion: (() -> Void)? = nil) {
    Task {
      var neededTitle = title
      var preferredStyle = UIAlertController.Style.alert
      var cancelStyle = UIAlertAction.Style.cancel
      if #available(iOS 26.0, *) {
        preferredStyle = source == nil ? .alert : .actionSheet
        cancelStyle = source == nil ? .cancel : .default
      } else {
        neededTitle = neededTitle ?? "Alert"
      }
      let alert = UIAlertController(title: neededTitle, message: message, preferredStyle: preferredStyle)
      alert.addAction(UIAlertAction(title: proceedTitle, style: proceedStyle) { _ in
        firstResponderAfterProceed?.becomeFirstResponder()
        completion?()
      })
      if let cancelTitle {
        alert.addAction(UIAlertAction(title: cancelTitle, style: cancelStyle))
      }
      alert.popoverPresentationController?.sourceItem = source
      showAlert(alert)
    }
  }
  
  func showMicrophoneAccessAlert() {
    showAlert("Aesthetics360 is not authorized to access the microphone.", title: "Microphone Error", proceedTitle: "Settings", cancelTitle: "Cancel") {
      Task {
        guard let settingsURL = URL(string: UIApplication.openSettingsURLString) else { return }
        UIApplication.shared.open(settingsURL)
      }
    }
  }
  
  func showInactivePatientAlert() {
    showAlert("This patient is marked as inactive. Reactivate their profile to begin a new consultation.", title: "Can’t Start Consultation", proceedTitle: "OK")
  }
  
  func showServerEnvironmentSelection(sourceView: UIView, onEnvironmentChanged: (() -> Void)? = nil) {
#if RELEASE
    return
#else
    let serverPreferenceKey = GlobalConstants.UserDefaultsKeys.server.rawValue
    let serverEnvironmentFromSettings = GlobalLinks.serverEnvironmentFromSettings
    let alertController = UIAlertController(title: "Select environment",
                                            message: "For development purposes only. Please use ‘Default’ unless you are familiar with environment configuration.\n\nCurrent URLs:\n\(GlobalLinks.serverEnvironment.baseHost)\n\(GlobalLinks.serverEnvironment.webSocketHost)\n\(GlobalLinks.serverEnvironment.baseWebViewHost)",
                                            preferredStyle: .actionSheet)
    
    alertController.popoverPresentationController?.sourceView = sourceView
    
    alertController.addAction(UIAlertAction(title: "Default (\(GlobalLinks.currentBuildServerEnvironment.name))",
                                            style: serverEnvironmentFromSettings == nil ? .destructive : .default) { _ in
      guard serverEnvironmentFromSettings != nil else { return }
      UserDefaults.standard.removeObject(forKey: serverPreferenceKey)
      onEnvironmentChanged?()
    })
    
    for environment in AnServerEnvironment.allCases {
      alertController.addAction(UIAlertAction(title: environment.name,
                                              style: serverEnvironmentFromSettings == environment ? .destructive : .default) { [weak self] _ in
        if environment != serverEnvironmentFromSettings {
          UserDefaults.standard.setValue(environment.rawValue, forKey: serverPreferenceKey)
        }
        
        if environment == .sandbox {
          self?.showSandboxServerEnvironmentSelection(onEnvironmentChanged: onEnvironmentChanged)
        } else {
          onEnvironmentChanged?()
        }
      })
    }
    alertController.addAction(UIAlertAction(title: "Cancel", style: .cancel))
    showAlert(alertController)
#endif
  }
  
  func showInternalBrowser(with url: URL?) {
    guard let url else { return }
    let safariViewController = SFSafariViewController(url: url)
    safariViewController.preferredBarTintColor = .surfaceSoft
    safariViewController.preferredControlTintColor = .primaryMedium
    safariViewController.dismissButtonStyle = .close
    safariViewController.modalPresentationStyle = .overFullScreen
    UIApplication.topViewController?.present(safariViewController, animated: true)
  }
  
  // MARK: - Private Functions
  
  private func dismissPreviousAlert(completion: @escaping (() -> Void)) {
    if let presentedAlert = UIApplication.topViewController?.presentedViewController as? UIAlertController {
      presentedAlert.dismiss(animated: false, completion: completion)
    } else {
      completion()
    }
  }
  
  private func showSandboxServerEnvironmentSelection(onEnvironmentChanged: (() -> Void)? = nil) {
    let baseHostKey = GlobalConstants.UserDefaultsKeys.sandboxBaseHost.rawValue
    let webSocketKey = GlobalConstants.UserDefaultsKeys.sandboxWebSocketHost.rawValue
    let baseWebViewHostKey = GlobalConstants.UserDefaultsKeys.sandboxBaseWebViewHost.rawValue
    
    let baseHost = UserDefaults.standard.string(forKey: baseHostKey).or(AnServerEnvironment.develop.baseHost)
    let webSocketHost = UserDefaults.standard.string(forKey: webSocketKey).or(AnServerEnvironment.develop.webSocketHost)
    let webViewHost = UserDefaults.standard.string(forKey: baseWebViewHostKey).or(AnServerEnvironment.develop.baseWebViewHost)
    
    let shortBaseHost = hostShorthand(from: baseHost)
    let shortWebSocketHost = hostShorthand(from: webSocketHost)
    let shortWebViewHost = hostShorthand(from: webViewHost)
    
    let alertController = UIAlertController(title: "Sandbox Environment",
                                            message: "Enter custom sandbox server hosts:\n\nAPI Host (dev or TICKET)\nWebSocket Host (dev or TICKET)\nWebView Host (dev or TICKET)",
                                            preferredStyle: .alert)
    
    addHostField(to: alertController, placeholder: "API Host (dev or TICKET)", value: shortBaseHost)
    addHostField(to: alertController, placeholder: "WebSocket Host (dev or TICKET)", value: shortWebSocketHost)
    addHostField(to: alertController, placeholder: "WebView Host (dev or TICKET)", value: shortWebViewHost)
    
    alertController.addAction(UIAlertAction(title: "Discard", style: .cancel) { _ in
      guard GlobalLinks.serverEnvironmentFromSettings != nil else { return }
      UserDefaults.standard.removeObject(forKey: GlobalConstants.UserDefaultsKeys.server.rawValue)
      onEnvironmentChanged?()
    })
    alertController.addAction(UIAlertAction(title: "Save", style: .default) { [weak self, weak alertController] _ in
      guard let self, let fields = alertController?.textFields, fields.count == 3 else { return }
      
      let baseHost = resolveFullHost(from: fields[0].text, devDefaultHost: AnServerEnvironment.develop.baseHost)
      let webSocketHost = resolveFullHost(from: fields[1].text, devDefaultHost: AnServerEnvironment.develop.webSocketHost)
      let webViewHost = resolveFullHost(from: fields[2].text, devDefaultHost: AnServerEnvironment.develop.baseWebViewHost)
      
      UserDefaults.standard.setValue(baseHost, forKey: baseHostKey)
      UserDefaults.standard.setValue(webSocketHost, forKey: webSocketKey)
      UserDefaults.standard.setValue(webViewHost, forKey: baseWebViewHostKey)
      
      onEnvironmentChanged?()
    })
    
    showAlert(alertController)
  }
  
  private func hostShorthand(from host: String) -> String {
    let parts = host.split(separator: ".").map { $0.lowercased() }
    if !host.contains("dev"), parts.count == 5, parts[2] == "sandbox", parts[3] == "aesthetics360", parts[4] == "com" {
      return parts[1]
    }
    return "dev"
  }
  
  private func resolveFullHost(from input: String?, devDefaultHost: String) -> String {
    let trimmed = input?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
    if trimmed.isEmpty || trimmed.lowercased() == "dev" {
      return devDefaultHost
    }
    let host = devDefaultHost.replacingOccurrences(of: "dev", with: "\(trimmed).sandbox")
    return host
  }
  
  private func addHostField(to alert: UIAlertController, placeholder: String, value: String?) {
    alert.addTextField { textField in
      textField.placeholder = placeholder
      textField.text = value
      textField.keyboardType = .URL
      textField.autocorrectionType = .no
      textField.autocapitalizationType = .none
      textField.clearButtonMode = .whileEditing
    }
  }
}
