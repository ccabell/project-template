//
//  AnPatientService.swift
//  A360Scribe
//
//  Created by Mike Grankin on 14.04.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

protocol AnPatientService {
  func loadPatients(searchText: String?, filter: AnPatientListFilter, pagination: AnPagination) async throws -> AnPatientListResponse
  func getPatient(_ patientId: String) async throws -> AnPatient
  func addPatient(parameters: AnPatientParams) async throws -> AnPatient
  func updatePatient(parameters: AnPatientParams) async throws -> AnPatient
  func updatePatientSummary(parameters: AnPatientSummaryParams) async throws -> AnPatient
  func loadConsultations(patientId: String, searchText: String?, filter: AnConsultationListFilter, pagination: AnPagination) async throws -> AnConsultationListResponse
}

extension AnAPIService: AnPatientService {
  func loadPatients(searchText: String?, filter: AnPatientListFilter, pagination: AnPagination) async throws -> AnPatientListResponse {
    var parameters = filter.parameters
    if let searchText, !searchText.isEmpty {
      parameters["search"] = searchText
    }
    parameters.merge(pagination.parameters) { _, new in new }
    let patientListResponse: AnPatientListResponse = try await performRequest(.getPatients, parameters: parameters)
    return patientListResponse
  }
  
  func getPatient(_ patientId: String) async throws -> AnPatient {
    try await performRequest(.getPatient(patientId: patientId), parameters: nil)
  }
  
  func addPatient(parameters: AnPatientParams) async throws -> AnPatient {
    let patient: AnPatient = try await performRequest(.addPatient, parameters: parameters.forRequest)
    return patient
  }
  
  func updatePatient(parameters: AnPatientParams) async throws -> AnPatient {
    guard let patientId = parameters.id else { throw AnError("Missing patient id") }
    let updatedPatient: AnPatient = try await performRequest(.updatePatient(patientId: patientId), parameters: parameters.forRequest)
    return updatedPatient
  }
  
  func updatePatientSummary(parameters: AnPatientSummaryParams) async throws -> AnPatient {
    let updatedPatient: AnPatient = try await performRequest(.updatePatient(patientId: parameters.id), parameters: parameters.forRequest)
    return updatedPatient
  }
  
  func loadConsultations(patientId: String, searchText: String?, filter: AnConsultationListFilter, pagination: AnPagination) async throws -> AnConsultationListResponse {
    var parameters: [String: Any] = ["patient_id": patientId]
    if let searchText, !searchText.isEmpty {
      parameters["search"] = searchText
    }
    parameters.merge(filter.parameters) { _, new in new }
    parameters.merge(pagination.parameters) { _, new in new }
    let consultationListResponse: AnConsultationListResponse = try await performRequest(.getConsultations, parameters: parameters)
    return consultationListResponse
  }
}
