//
//  AnSessionManager.swift
//  A360Scribe
//
//  Created by Mike Grankin on 31.01.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import Foundation

final class AnSessionManager {
  
  // MARK: - Public Properties
  
  static let shared = AnSessionManager()
  var token: AnToken?
  
  // MARK: - Private Properties
  
  private var refreshTask: Task<String, Error>?
  private lazy var authService: AnAuthService = AnAPIService()
  
  // MARK: - Public Functions
  
  func logout() {
    cleanup()
    reset()
  }
  
  func getValidAuthHeader() async throws -> String {
    if let token, !token.isExpired {
      return token.authHttpHeaderValue
    }
    
    if let refreshTask {
      return try await refreshTask.value
    }
    
    let task = Task<String, Error> {
      defer { refreshTask = nil }
      return try await refreshAndReturnHeader()
    }
    
    refreshTask = task
    return try await task.value
  }
  
  // MARK: - Private Functions
  
  private func refreshAndReturnHeader() async throws -> String {
    guard let refreshToken = token?.refreshToken else {
      throw AnError("Your session is expired. Please login again.")
    }
    
    let newToken = try await authService.refresh(refreshToken: refreshToken)
    return newToken.authHttpHeaderValue
  }
  
  private func reset() {
    token = nil
  }
  
  private func cleanup() {
    AnUserManager.shared.clearCurrentUser()
    guard let directoryURL = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first,
          let content = try? FileManager.default.contentsOfDirectory(at: directoryURL, includingPropertiesForKeys: nil)
    else { return }
    
    for item in content {
      try? FileManager.default.removeItem(at: item)
    }
  }
}
