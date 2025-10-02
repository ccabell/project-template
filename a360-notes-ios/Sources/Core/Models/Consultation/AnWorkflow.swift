//
//  AnWorkflow.swift
//  A360Scribe
//
//  Created by Mike Grankin on 19.08.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

struct AnWorkflow: Codable, AnDisplayable {
  let id: String
  let name: String
  var displayTitle: String { name }
}

struct AnWorkflowResponse: Codable, AnPaginatedResponseProtocol {
  let total: Int
  let page: Int
  let size: Int
  let items: [AnWorkflow]
}
