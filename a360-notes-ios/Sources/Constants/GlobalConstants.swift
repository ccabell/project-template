//
//  GlobalConstants.swift
//  A360Scribe
//
//  Created by Mike Grankin on 25.02.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import Foundation

final class GlobalConstants {
  
  enum InactivityTimeout: TimeInterval {
    case logoutAfter = 900.0
    case idleWarningAfter = 780.0
  }
  
  static let logoutTimerBannerId = "LogoutTimerBanner"
  
  // MARK: - Http Headers
  
  enum HttpHeaders: String {
    case contentType = "Content-Type"
    case authorization = "Authorization"
    case userAgent = "User-Agent"
  }
  
  // MARK: - User Defaults Keys
  
  enum UserDefaultsKeys: String {
    case server = "server_preference"
    case storedUsers = "stored_users"
    case sandboxBaseHost = "sandbox_base_host"
    case sandboxWebSocketHost = "sandbox_websocket_host"
    case sandboxBaseWebViewHost = "sandbox_base_webview_host"
  }
  
  // MARK: - Keychain Keys
  
  enum KeychainKeys: String {
    case aesEncryptionKey = "com.aesthetics360.scribe.aesEncryptionKey"
  }
  
  static let bannerDuration: TimeInterval = 5.0
  static let loginErrorBannerDuration: TimeInterval = 15.0
  static let dummyId = "00000000-0000-0000-0000-000000000000"
  static var defaultPageSize = 20
  static var largePageSize = 100
  
  enum Notifications {
    case performLogout
    var name: NSNotification.Name {
      switch self {
      case .performLogout:
        return NSNotification.Name(rawValue: "performLogout")
      }
    }
  }
}
