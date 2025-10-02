//
//  AnWebViewBridge.swift
//  A360Scribe
//
//  Created by Mike Grankin on 21.04.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import WebKit

@MainActor
class AnWebViewBridge: NSObject, WKScriptMessageHandler {
  
  // MARK: - Public Properties
  
  var onError: ((Error) -> Void)?
  
  // MARK: - Private Properties
  
  private weak var webView: WKWebView?
  
  // MARK: - Overridable Properties
  
  /// Subclasses override this to supply the list of `WKScriptMessage` names they care about.
  internal var scriptMessageNames: [String] { [] }
  
  // MARK: - Lifecycle
  
  init(webView: WKWebView) {
    self.webView = webView
    super.init()
    registerScriptHandlers()
  }
  
  deinit {
    let webView = self.webView
    Task { @MainActor in
      webView?.configuration.userContentController.removeAllScriptMessageHandlers()
    }
  }
  
  // MARK: - Public Functions
  
  func send<E: AnWebViewEvent>(_ event: E) {
    Task {
      let js: String
      do {
        let data = try JSONEncoder().encode(event.payload)
        guard let jsonString = String(data: data, encoding: .utf8) else {
          throw AnError("Failed to encode payload")
        }
        js = "window.dispatchEvent(new CustomEvent('\(event.name)', { detail: \(jsonString) }));"
        try await evaluate(js)
      } catch {
        onError?(error)
      }
    }
  }
  
  func send(name: String) {
    Task {
      do {
        let js = "window.dispatchEvent(new CustomEvent('\(name)'));"
        try await evaluate(js)
      } catch {
        onError?(error)
      }
    }
  }
  
  /// Override in subclasses to handle JS → Swift messages.
  /// Default implementation does nothing.
  func handleScriptMessage(name: String, body: Any) {}
  
  // MARK: - Private Functions
  
  private func evaluate(_ js: String) async throws {
    guard let webView else { return }
    try await withCheckedThrowingContinuation { (continuation: CheckedContinuation<Void, Error>) in
      webView.evaluateJavaScript(js) { _, error in
        if let error {
          self.onError?(error)
          continuation.resume(throwing: error)
        } else {
          continuation.resume()
        }
      }
    }
  }
  
  private func registerScriptHandlers() {
    guard let webView else { return }
    Task {
      scriptMessageNames.forEach {
        webView.configuration.userContentController.add(self, name: $0)
      }
    }
  }
  
  // MARK: - WKScriptMessageHandler
  
  func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
    handleScriptMessage(name: message.name, body: message.body)
  }
}
