//
//  AnAuthService.swift
//  A360Scribe
//
//  Created by Mike Grankin on 28.03.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

protocol AnAuthService {
  func login(username: String, password: String) async throws
  func refresh(refreshToken: String) async throws -> AnToken
}

extension AnAPIService: AnAuthService {
  func login(username: String, password: String) async throws {
    let parameters: [String: Any] = ["grant_type": "password",
                                     "client_id": GlobalLinks.serverEnvironment.appClientId,
                                     "username": username,
                                     "password": password]
    
    let token: AnToken = try await performRequest(.login, parameters: parameters)
    AnSessionManager.shared.token = token
  }
  
  func refresh(refreshToken: String) async throws -> AnToken {
    let parameters: [String: Any] = ["grant_type": "refresh_token",
                                     "client_id": GlobalLinks.serverEnvironment.appClientId,
                                     "refresh_token": refreshToken]
    
    let token: AnToken = try await performRequest(.refreshToken, parameters: parameters)
    AnSessionManager.shared.token = token
    return token
  }
}
