//
//  AnWebViewEvent.swift
//  A360Scribe
//
//  Created by Mike Grankin on 21.04.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

protocol AnWebViewEvent {
  associatedtype Payload: AnWebViewPayload
  var name: String { get }
  var payload: Payload { get }
}
