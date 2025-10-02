//
//  AnWebSocketEventResponse.swift
//  A360Scribe
//
//  Created by Mike Grankin on 24.04.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

struct AnWebSocketEventResponse: Codable {
  let event: AnWebSocketEvent
}

enum AnWebSocketEvent: String, Codable {
  case keepAlive = "ka"
}
