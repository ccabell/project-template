//
//  AnBioAuthManager.swift
//  A360Scribe
//
//  Created by Mike Grankin on 08.05.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import UIKit
import LocalAuthentication

final class AnBioAuthManager {
  
  // MARK: - Public Properties
  
  static let shared = AnBioAuthManager()
  
  public lazy var biometryName = biometryType == .faceID ? "Face ID" : "Touch ID"
  public lazy var actionTitle = "Use \(biometryName)"
  public lazy var symbolName = biometryType == .faceID ? "faceid" : "touchid"
  public lazy var icon = {
    guard let image = UIImage(systemName: symbolName)
    else { return UIImage() }
    return image
  }()
  
  public var isBiometryAvailable: Bool {
    let context = LAContext()
    var error: NSError?
    return context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error)
  }
  
  public var biometryType: LABiometryType {
    let context = LAContext()
    _ = context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: nil)
    return context.biometryType
  }
  
  // MARK: - Public Functions
  
  public func authenticateUser() async throws {
    let reason = "Authenticate with \(biometryName)"
    let context = LAContext()
    context.localizedCancelTitle = "Cancel"
    var throwingError: Error?
    
    do {
      try await context.evaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, localizedReason: reason)
    } catch let laError as LAError {
      try await UIApplication.shared.waitUntilActiveIfNeeded()
      switch laError.code {
      case .authenticationFailed:
        throwingError = AnError("Authentication unsuccessful: invalid credentials.")
      case .passcodeNotSet:
        throwingError = AnError("No passcode is configured on this device.")
      case .biometryNotAvailable:
        throwingError = AnError("Biometric authentication not supported.")
      case .biometryLockout:
        throwingError = AnError("Biometry locked after too many failed attempts.")
      default:
        throwingError = AnError("Authentication failed. Please try again.")
      }
    } catch let anError as AnError {
      throwingError = anError
    } catch {
      throwingError = AnError("Authentication failed. Please try again.")
    }
    try await UIApplication.shared.waitUntilActiveIfNeeded()
    
    if let throwingError {
      throw throwingError
    }

  }
}
