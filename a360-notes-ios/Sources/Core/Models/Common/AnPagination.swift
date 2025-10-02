//
//  AnPagination.swift
//  A360Scribe
//
//  Created by Mike Grankin on 11.07.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

struct AnPagination {
  var page: Int = 1
  var size: Int = GlobalConstants.defaultPageSize
  var hasMorePages: Bool = true
  
  var parameters: [String: Any] {
    return ["page": page, "size": size]
  }

  mutating func update(basedOn response: AnPaginatedResponseProtocol) {
    hasMorePages = response.page * response.size < response.total
    page = response.page + 1
  }
}
