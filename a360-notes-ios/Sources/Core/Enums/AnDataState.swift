//
//  AnDataState.swift
//  A360Scribe
//
//  Created by Mike Grankin on 10.04.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

enum AnDataState {
  case noData
  case noSearchResults
  case loading
  case loadingMore
  case dataAvailable
  
  var hasData: Bool {
    return [.dataAvailable, .loadingMore].contains(self)
  }
}
