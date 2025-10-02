//
//  AnJSONDecoder.swift
//  A360Scribe
//
//  Created by Mike Grankin on 08.07.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import Foundation

final class AnJSONDecoder: JSONDecoder, @unchecked Sendable {

  override init() {
    super.init()
    dateDecodingStrategy = .custom { decoder in
      let container = try decoder.singleValueContainer()
      guard let dateString = try? container.decode(String.self),
            let date = AnDateFormatter.shared.convert(dateString: dateString, from: .serverDateTime)
      else {
        throw DecodingError.dataCorruptedError(in: container, debugDescription: "Cannot decode date value")
      }
      return date
    }
  }
}
