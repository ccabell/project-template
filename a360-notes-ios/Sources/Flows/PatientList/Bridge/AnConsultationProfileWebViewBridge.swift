//
//  AnConsultationProfileWebViewBridge.swift
//  A360Scribe
//
//  Created by Mike Grankin on 06.06.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

@MainActor
final class AnConsultationProfileWebViewBridge: AnWebViewBridge {

  // MARK: - Public Properties
  
  var onEvent: ((WebEvent) -> Void)?
  
  // MARK: - Overridable Properties
  
  override internal var scriptMessageNames: [String] { WebEvent.allNames }
  
  // MARK: - JS → Swift
  
  override func handleScriptMessage(name: String, body: Any) {
    guard let event = WebEvent(name: name, body: body) else { return }
    onEvent?(event)
  }
  
  // MARK: - Swift → JS (sending events)

  static let appDidEnterBackgroundEventName = "anEventAppDidEnterBackground"
  static let appDidBecomeActiveEventName = "anEventAppDidBecomeActive"
  static let closeFeedbackModalEventName = "anEventCloseFeedbackModal"

  // MARK: - Web Events
  
  enum WebEvent: String, CaseIterable {
    case openUnsavedFeedbackChangesAlert = "anEventOpenUnsavedFeedbackChangesAlert"
    case contentDidLoad = "anEventContentDidLoad"

    static var allNames: [String] {
      allCases.map(\.rawValue)
    }

    init?(name: String, body _: Any) {
      self.init(rawValue: name)
    }
  }
}
