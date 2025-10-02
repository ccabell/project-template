//
//  AnWebSocketSummaryResponse.swift
//  A360Scribe
//
//  Created by Mike Grankin on 25.04.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

struct AnWebSocketSummaryResponse: Codable {
  let status: String
  let summary: String?
  let finished: Bool
  
  enum CodingKeys: String, CodingKey {
    case status
    case summary
    case finished = "session_finished"
  }
}
