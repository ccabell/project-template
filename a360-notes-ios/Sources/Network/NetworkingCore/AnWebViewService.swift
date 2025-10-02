//
//  AnWebViewService.swift
//  A360Scribe
//
//  Created by Mike Grankin on 16.04.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import UIKit

final class AnWebViewService {
  func generateURL(for provider: AnWebViewProvider) -> URL {
    var components = URLComponents()
    components.scheme = "https"
    components.host = GlobalLinks.serverEnvironment.baseWebViewHost
    components.path = provider.path
    
    var queryItems = defaultQueryItems()
    queryItems.append(contentsOf: provider.queryItems)
    
    components.queryItems = queryItems
    
    guard let url = components.url else {
      fatalError("Invalid WebView URL for provider: \(provider)")
    }
    
    return url
  }
  
  // MARK: - Private Functions
  
  private func defaultQueryItems() -> [URLQueryItem] {
    guard let token = AnSessionManager.shared.token else {
      fatalError("Token missing from session")
    }
    
    let role = AnUserManager.shared.currentUser?.role ?? .admin
    let practiceAccountType = AnUserManager.shared.currentUser?.practiceAccountType ?? .live
    let creationDateMs = Int(token.creationDate.timeIntervalSince1970 * 1000)
    let idiom = UIDevice.current.userInterfaceIdiom == .pad ? "iPad" : "iPhone"
    let osVersion = UIDevice.current.systemVersion
    let platform = UIDevice.current.systemName
    
    return [.init(name: "accessToken", value: token.accessToken.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed)),
            .init(name: "expiresIn", value: "\(token.expiresIn)"),
            .init(name: "creationDate", value: "\(creationDateMs)"),
            .init(name: "userRole", value: role.rawValue.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed)),
            .init(name: "practiceAccountType", value: "\(practiceAccountType.rawValue)"),
            .init(name: "hash", value: "\(Date().timeIntervalSince1970)"),
            .init(name: "platform", value: platform),
            .init(name: "deviceIdiom", value: idiom),
            .init(name: "osVersion", value: osVersion)]
  }
}
