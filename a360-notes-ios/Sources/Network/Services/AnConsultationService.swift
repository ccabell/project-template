//
//  AnConsultationService.swift
//  A360Scribe
//
//  Created by Mike Grankin on 27.03.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

protocol AnConsultationService {
  func initiate(patient: AnPatient) async throws -> AnConsultation
  func update(consultationId: String, status: AnConsultationStatus) async throws -> AnConsultation
}

extension AnAPIService: AnConsultationService {
  func initiate(patient: AnPatient) async throws -> AnConsultation {
    let expertId = AnUserManager.shared.currentUser?.expertId
    let parameters: [String: Any] = ["patient_id": patient.id,
                                     "expert_id": expertId as Any,
                                     "workflow_id": GlobalConstants.dummyId,
                                     "consultation_status": AnConsultationStatus.idle.rawValue]
    
    let consultation: AnConsultation = try await performRequest(.initiateConsultation, parameters: parameters)
    return consultation
  }
  
  func update(consultationId: String, status: AnConsultationStatus) async throws -> AnConsultation {
    let provider = AnAPIProvider.updateConsultationStatus(consultationId: consultationId)
    let parameters: [String: Any] = ["consultation_status": status.rawValue]
    let consultation: AnConsultation = try await performRequest(provider, parameters: parameters)
    return consultation
  }
}
