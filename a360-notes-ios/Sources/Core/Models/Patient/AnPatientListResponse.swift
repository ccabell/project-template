//
//  AnPatientListResponse.swift
//  A360Scribe
//
//  Created by Mike Grankin on 14.04.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

struct AnPatientListResponse: Codable, AnPaginatedResponseProtocol {
  let total: Int
  let page: Int
  let size: Int
  let items: [AnPatient]
}
