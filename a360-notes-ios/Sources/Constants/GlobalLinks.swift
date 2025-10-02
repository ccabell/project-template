//
//  GlobalLinks.swift
//  A360Scribe
//
//  Created by Mike Grankin on 25.02.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import Foundation

// MARK: - Enums

enum AnServerEnvironment: String, CaseIterable, Codable {
  case develop
  case staging
  case production
  case sandbox
  
  var baseHost: String {
    switch self {
    case .develop:
      return "api.dev.aesthetics360.com"
    case .staging:
      return "api.staging.aesthetics360.com"
    case .production:
      return "api.app.aesthetics360.com"
    case .sandbox:
      let sandboxBaseHost = UserDefaults.standard.string(forKey: GlobalConstants.UserDefaultsKeys.sandboxBaseHost.rawValue).or(Self.develop.baseHost)
      return sandboxBaseHost
    }
  }
  
  var webSocketHost: String {
    switch self {
    case .develop:
      return "ws.dev.aesthetics360.com"
    case .staging:
      return "ws.staging.aesthetics360.com"
    case .production:
      return "ws.app.aesthetics360.com"
    case .sandbox:
      let sandboxWebSocketHost = UserDefaults.standard.string(forKey: GlobalConstants.UserDefaultsKeys.sandboxWebSocketHost.rawValue).or(Self.develop.webSocketHost)
      return sandboxWebSocketHost
    }
  }
  
  var baseWebViewHost: String {
    switch self {
    case .develop:
      return "app.dev.aesthetics360.com"
    case .staging:
      return "app.staging.aesthetics360.com"
    case .production:
      return "app.aesthetics360.com"
    case .sandbox:
      let sandboxBaseWebViewHost = UserDefaults.standard.string(forKey: GlobalConstants.UserDefaultsKeys.sandboxBaseWebViewHost.rawValue).or(Self.develop.baseWebViewHost)
      return sandboxBaseWebViewHost
    }
  }
  
  var appClientId: String {
    switch self {
    case .develop, .sandbox:
      return "644pg0avlot7qpppj96h0l362k"
    case .staging:
      return "654kvhns3bqbc93qdkrpdivm6n"
    case .production:
      return "4o2kdii07c0k510u8upa36e846"
    }
  }
  
  var storageKey: String {
    switch self {
    case .develop, .sandbox:
      return "dev"
    case .staging:
      return "stage"
    case .production:
      return "prod"
    }
  }
  
  var name: String {
    switch self {
    case .develop:
      return "Develop"
    case .staging:
      return "Staging"
    case .production:
      return "Production"
    case .sandbox:
      return "Sandbox"
    }
  }
}

// MARK: - GlobalLinks

final class GlobalLinks {
  
  static var serverEnvironmentFromSettings: AnServerEnvironment? {
    guard let serverEnvironmentValue = UserDefaults.standard.string(forKey: GlobalConstants.UserDefaultsKeys.server.rawValue),
          let serverEnvironmentFromSettings = AnServerEnvironment(rawValue: serverEnvironmentValue)
    else { return nil }
    return serverEnvironmentFromSettings
  }
  
  static var serverEnvironment: AnServerEnvironment {
#if RELEASE
    return currentBuildServerEnvironment
#else
    return serverEnvironmentFromSettings ?? currentBuildServerEnvironment
#endif
  }
  
  static var serverBaseUrl: String {
    let urlString = "https://\(serverEnvironment.baseHost)/"
    return urlString
  }
  
  static var webSocketUrl: String {
    let urlString = "wss://\(serverEnvironment.webSocketHost)/transcription/ws"
    return urlString
  }
  
  static var currentBuildServerEnvironment: AnServerEnvironment {
#if DEBUG
    return .develop
#elseif TESTING
    return .staging
#elseif RELEASE
    return .production
#else
    fatalError("No valid build configuration flag set.")
#endif
  }
  
  enum ExternalLinks {
    case loginSupport
    
    var url: URL? {
      switch self {
      case .loginSupport:
        return URL(string: "https://support.aesthetics360.com/login-support")
      }
    }
  }
}
