//
//  AnEncryptManager.swift
//  A360Scribe
//
//  Created by Mike Grankin on 07.04.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import Foundation
import CryptoKit

final class AnEncryptManager {
  
  // MARK: - Public Properties
  
  static let shared = AnEncryptManager()
  
  // MARK: - Private Properties
  
  private let keyIdentifier = GlobalConstants.KeychainKeys.aesEncryptionKey.rawValue
  
  private lazy var secureEncryptKey: SymmetricKey = {
    guard let storedKey else {
      let newKey = SymmetricKey(size: .bits256)
      saveSecureEncryptKey(keyData: newKey.withUnsafeBytes { Data($0) })
      return newKey
    }
    return storedKey
  }()
  
  private var storedKey: SymmetricKey? {
    let query: [String: Any] = [
      kSecClass as String: kSecClassGenericPassword,
      kSecAttrAccount as String: keyIdentifier,
      kSecReturnData as String: kCFBooleanTrue as Any
    ]
    
    var storedKeyObject: AnyObject?
    let status = SecItemCopyMatching(query as CFDictionary, &storedKeyObject)
    
    guard status == errSecSuccess, let storedKeyData = storedKeyObject as? Data else {
      return nil
    }
    
    return SymmetricKey(data: storedKeyData)
  }
  
  // MARK: - Private Functions
  
  private func saveSecureEncryptKey(keyData: Data) {
    let query = [kSecClass: kSecClassGenericPassword,
           kSecAttrAccount: keyIdentifier,
             kSecValueData: keyData,
            kSecReturnData: kCFBooleanTrue as Any]
    
    SecItemDelete(query as CFDictionary)
    let status = SecItemAdd(query as CFDictionary, nil)
    
    if status != errSecSuccess {
      print("Keychain: Failed to save encryption key.")
    }
  }
  
  // MARK: - Public Functions
  
  func encrypt(_ data: Data) -> Data? {
    do {
      let sealedBox = try AES.GCM.seal(data, using: secureEncryptKey)
      return sealedBox.combined
    } catch {
      print("Encryption error: \(error.localizedDescription)")
      return nil
    }
  }
  
  func decrypt(_ data: Data) -> Data? {
    do {
      let sealedBox = try AES.GCM.SealedBox(combined: data)
      return try AES.GCM.open(sealedBox, using: secureEncryptKey)
    } catch {
      print("Decryption error: \(error.localizedDescription)")
      return nil
    }
  }
  
  func encrypt<T: Codable>(_ object: T) -> Data? {
    do {
      let data = try JSONEncoder().encode(object)
      return encrypt(data)
    } catch {
      print("Encryption encoding error: \(error)")
      return nil
    }
  }
  
  func decrypt<T: Codable>(_ data: Data) -> T? {
    guard let decryptedData = decrypt(data) else { return nil }
    do {
      return try JSONDecoder().decode(T.self, from: decryptedData)
    } catch {
      print("Decryption decoding error: \(error)")
      return nil
    }
  }
}
