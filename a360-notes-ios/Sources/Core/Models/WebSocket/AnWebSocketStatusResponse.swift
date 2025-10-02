//
//  AnWebSocketStatusResponse.swift
//  A360Scribe
//
//  Created by Mike Grankin on 18.03.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

struct AnWebSocketStatusResponse: Codable {
  let status: AnWebSocketStatus
  let error: String?
}

enum AnWebSocketStatus: String, Codable {
  case connected
  case authenticated
  case attached
  case ok
  case error
  case disconnected
  case unknown
  
  init(from rawValue: String) {
    self = AnWebSocketStatus(rawValue: rawValue) ?? .unknown
  }
}
