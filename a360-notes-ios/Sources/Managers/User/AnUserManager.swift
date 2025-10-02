//
//  AnUserManager.swift
//  A360Scribe
//
//  Created by Mike Grankin on 07.04.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import Foundation

final class AnUserManager {
  
  // MARK: - Public Properties
  
  static let shared = AnUserManager()
  private(set) var currentUser: AnUser?
  
  // MARK: - Public Functions
  
  func saveOrUpdate(_ user: AnUser) {
    var allUsers = loadAllUsers()
    let key = makeStorageKey(for: user.username, in: user.serverEnvironment)
    let userToSave: AnUser

    if var existingUser = allUsers[key] {
      existingUser.info.update(from: user.info)
      userToSave = existingUser
    } else {
      userToSave = user
    }

    allUsers[key] = userToSave
    persist(allUsers)
    currentUser = userToSave
  }
  
  func loadUser(username: String) -> AnUser? {
    let key = makeStorageKey(for: username, in: GlobalLinks.serverEnvironment)
    let allUsers = loadAllUsers()
    let user = allUsers[key]
    return user
  }
  
  func recentUsers() -> [AnUser]? {
    let allUsers = loadAllUsers()
    var filteredUsers = allUsers.filter { $0.key.hasSuffix("__\(GlobalLinks.serverEnvironment.storageKey)") }.map(\.value)
    filteredUsers.sort { $0.lastLogin > $1.lastLogin }
    return filteredUsers
  }
  
  func getLastLoggedInUser() -> AnUser? {
    let filteredUsers = recentUsers()
    let lastUser = filteredUsers?.first
    return lastUser
  }
  
  func deleteUser(username: String) {
    let key = makeStorageKey(for: username, in: GlobalLinks.serverEnvironment)
    var users = loadAllUsers()
    users.removeValue(forKey: key)
    persist(users)
  }
  
  func clearCurrentUser() {
    currentUser = nil
  }
  
  // MARK: - Private Functions
  
  private func makeStorageKey(for username: String, in environment: AnServerEnvironment) -> String {
    return "\(username.lowercased())__\(environment.storageKey)"
  }
  
  private func loadAllUsers() -> [String: AnUser] {
    guard let encryptedData = UserDefaults.standard.data(forKey: GlobalConstants.UserDefaultsKeys.storedUsers.rawValue),
          let users: [String: AnUser] = AnEncryptManager.shared.decrypt(encryptedData) else {
      return [:]
    }
    return users
  }
  
  private func persist(_ users: [String: AnUser]) {
    guard let encrypted = AnEncryptManager.shared.encrypt(users) else {
      print("Failed to encrypt user dictionary")
      return
    }
    UserDefaults.standard.set(encrypted, forKey: GlobalConstants.UserDefaultsKeys.storedUsers.rawValue)
  }
}
