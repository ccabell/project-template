//
//  AnAPIProvider.swift
//  A360Scribe
//
//  Created by Mike Grankin on 27.02.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import UIKit

enum AnAPIProvider {
  
  // MARK: - Auth
  
  case login
  case refreshToken
  
  // MARK: - Practice
  
  case userProfile
  case getAllEnums
  case getExperts
  case getWorkflows
  
  // MARK: - Patient
  
  case getPatients
  case getPatient(patientId: String)
  case addPatient
  case updatePatient(patientId: String)
  case getConsultations
  
  // MARK: - Consultation
  
  case initiateConsultation
  case updateConsultationStatus(consultationId: String)
  
  // MARK: - Private Properties
  
  private var path: String {
    switch self {
    case .login, .refreshToken:
      return "services/oauth2/token"
    case .userProfile:
      return "services/practice/profile"
    case .getExperts:
      return "services/practice/experts"
    case .getWorkflows:
      return "services/practice/consultation_workflows"
    case .getAllEnums:
      return "services/patient/enums"
    case .getPatients, .addPatient:
      return "services/patient/patients"
    case .getPatient(let patientId), .updatePatient(let patientId):
      return "services/patient/patients/\(patientId)"
    case .getConsultations:
      return "services/patient/consultations"
    case .initiateConsultation:
      return "services/patient/consultations"
    case .updateConsultationStatus(let consultationId):
      return "services/patient/consultations/\(consultationId)"
    }
  }
  
  // MARK: - Public Properties
  
  var url: URL {
    guard let url = URL(string: "\(GlobalLinks.serverBaseUrl)\(path)") else {
      fatalError("Invalid URL: \(GlobalLinks.serverBaseUrl)\(path)")
    }
    return url
  }
  
  var method: String {
    switch self {
    case .userProfile, .getAllEnums, .getExperts, .getWorkflows, .getPatients, .getPatient, .getConsultations:
      return "GET"
    case .login, .refreshToken, .addPatient, .initiateConsultation:
      return "POST"
    case .updatePatient, .updateConsultationStatus:
      return "PATCH"
    }
  }
  
  var contentType: AnHTTPContentType {
    switch self {
    case .login, .refreshToken:
      return .formURLEncoded
    case .userProfile, .getAllEnums, .getExperts, .getWorkflows, .getPatients, .getPatient, .addPatient, .updatePatient, .getConsultations, .initiateConsultation, .updateConsultationStatus:
      return .json
    }
  }
  
  var parameterEncoding: AnParameterEncoding {
    switch self {
    case .userProfile, .getPatients, .getConsultations:
      return .urlEncoded
    case .login, .refreshToken, .getAllEnums, .getExperts, .getWorkflows, .getPatient, .addPatient, .updatePatient, .initiateConsultation, .updateConsultationStatus:
      return .jsonEncoded
    }
  }
  
  var staticHeaders: [String: String] {
    return [GlobalConstants.HttpHeaders.contentType.rawValue: contentType.rawValue,
            GlobalConstants.HttpHeaders.userAgent.rawValue: makeUserAgent()]
  }
  
  var requiresAuth: Bool {
    switch self {
    case .login, .refreshToken:
      return false
    default:
      return true
    }
  }
  
  // MARK: - Private Functions
  
  private func makeUserAgent() -> String {
#if DEBUG
    let debug = "DEBUG-"
#else
    let debug = ""
#endif
    let executable = Bundle.main.infoDictionary?[kCFBundleExecutableKey as String] as? String ?? ""
    let appVersion = Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? ""
    let appBuild = Bundle.main.infoDictionary?[kCFBundleVersionKey as String] as? String ?? ""
    let device = UIDevice.current.modelName
    let osNameVersion = "\(UIDevice.current.systemName) \(UIDevice.current.systemVersion)"
    return "\(debug)\(executable)/\(appVersion) (\(appBuild)) (\(device); \(osNameVersion))"
  }
}

enum AnHTTPContentType: String {
  case json = "application/json"
  case formURLEncoded = "application/x-www-form-urlencoded"
}

enum AnParameterEncoding {
  case urlEncoded
  case jsonEncoded
}
