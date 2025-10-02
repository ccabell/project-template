//
//  AnPaginatedResponseProtocol.swift
//  A360Scribe
//
//  Created by Mike Grankin on 11.07.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

protocol AnPaginatedResponseProtocol {
  var total: Int { get }
  var page: Int { get }
  var size: Int { get }
}
