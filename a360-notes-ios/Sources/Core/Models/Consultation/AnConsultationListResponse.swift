//
//  AnConsultationListResponse.swift
//  A360Scribe
//
//  Created by Mike Grankin on 13.08.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

struct AnConsultationListResponse: Codable, AnPaginatedResponseProtocol {
  let total: Int
  let page: Int
  let size: Int
  let items: [AnConsultation]
}
