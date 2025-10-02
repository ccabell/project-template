//
//  AnPracticeService.swift
//  A360Scribe
//
//  Created by Mike Grankin on 08.04.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

protocol AnPracticeService {
  func userProfile() async throws -> AnUserProfile
  func fetchAllEnums() async throws -> AnAllEnumsResponse
  func getExperts() async throws -> [AnExpert]
  func getWorkflows() async throws -> [AnWorkflow]
}

extension AnAPIService: AnPracticeService {
  func userProfile() async throws -> AnUserProfile {
    try await performRequest(.userProfile)
  }
  
  func fetchAllEnums() async throws -> AnAllEnumsResponse {
    try await performRequest(.getAllEnums)
  }
  
  func getExperts() async throws -> [AnExpert] {
    let pagination = AnPagination(page: 1, size: GlobalConstants.largePageSize)
    let parameters = pagination.parameters
    let expertResponse: AnExpertResponse = try await performRequest(.getExperts, parameters: parameters)
    return expertResponse.items
  }
  
  func getWorkflows() async throws -> [AnWorkflow] {
    let pagination = AnPagination(page: 1, size: GlobalConstants.largePageSize)
    let parameters = pagination.parameters
    let workflowResponse: AnWorkflowResponse = try await performRequest(.getWorkflows, parameters: parameters)
    return workflowResponse.items
  }
}
