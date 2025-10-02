//
//  AnConsultationWebViewBridge.swift
//  A360Scribe
//
//  Created by Mike Grankin on 21.04.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import Foundation
import WebKit

@MainActor
final class AnConsultationWebViewBridge: AnWebViewBridge {
  
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
  
  struct SetActiveTabEvent: AnWebViewEvent {
    struct Payload: AnWebViewPayload {
      let activeTab: String
    }
    
    let payload: Payload
    var name: String { "anEventSetActiveTab" }
  }
  
  // MARK: - Web Events
  
  enum WebEvent {
    case updateTabContent(AnConsultationTab)
    
    private enum EventType: String, CaseIterable {
      case updateTabContent = "anEventUpdateTabContent"
    }
    
    static var allNames: [String] {
      EventType.allCases.map(\.rawValue)
    }
    
    init?(name: String, body: Any) {
      switch name {
      case EventType.updateTabContent.rawValue:
        guard let payload = body as? [String: Any],
              let tabRaw = payload["tab"] as? String,
              let tab = AnConsultationTab(rawValue: tabRaw)
        else { return nil }
        self = .updateTabContent(tab)
        
      default:
        return nil
      }
    }
  }
}
