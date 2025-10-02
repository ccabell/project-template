//
//  AnAPIService.swift
//  A360Scribe
//
//  Created by Mike Grankin on 27.03.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

import Foundation

protocol AnAPIExecutable {
  func performRequest<T: Decodable>(_ provider: AnAPIProvider, parameters: [String: Any?]?) async throws -> T
  func performRequest(_ provider: AnAPIProvider, parameters: [String: Any?]?) async throws -> [String: Any]
}

class AnAPIService: AnAPIExecutable {
  
  // MARK: - Public Functions
  
  func performRequest<T: Decodable>(_ provider: AnAPIProvider, parameters: [String: Any?]? = nil) async throws -> T {
    let json = try await performRequest(provider, parameters: parameters)
    let data = try JSONSerialization.data(withJSONObject: json)
    
    do {
      let decodedResponse = try AnJSONDecoder().decode(T.self, from: data)
      return decodedResponse
    } catch let decodingError as DecodingError {
      throw makeDescriptiveDecodingError(decodingError, type: T.self)
    } catch {
      throw error
    }
  }
  
  func performRequest(_ provider: AnAPIProvider, parameters: [String: Any?]? = nil) async throws -> [String: Any] {
    guard let request = try await makeRequest(from: provider, parameters: parameters) else {
      throw AnError("Invalid request.")
    }
    
    let (data, response) = try await URLSession.shared.data(for: request)
    
    guard let httpResponse = response as? HTTPURLResponse else {
      throw AnError("Invalid server response.")
    }
    
    let jsonObject = try? JSONSerialization.jsonObject(with: data)
    let statusCode = httpResponse.statusCode
    
    switch statusCode {
    case 200...299:
      if let json = jsonObject as? [String: Any] {
        return json
      } else {
        throw AnError("Empty or invalid response.", statusCode: statusCode)
      }
      
    default:
      if let json = jsonObject as? [String: Any], let detail = json["detail"] {
        throw AnError(detail, statusCode: statusCode)
      }
      if let message = String(data: data, encoding: .utf8) {
        throw AnError(message, statusCode: statusCode)
      }
      throw AnError("Something went wrong.", statusCode: statusCode)
    }
  }
  
  // MARK: - Private Functions
  
  private func makeRequest(from provider: AnAPIProvider, parameters: [String: Any?]?) async throws -> URLRequest? {
    var request = URLRequest(url: provider.url)
    request.httpMethod = provider.method
    
    provider.staticHeaders.forEach { key, value in
      request.setValue(value, forHTTPHeaderField: key)
    }
    
    if provider.requiresAuth {
      let authHeader = try await AnSessionManager.shared.getValidAuthHeader()
      request.setValue(authHeader, forHTTPHeaderField: GlobalConstants.HttpHeaders.authorization.rawValue)
    }
    
    guard let parameters else { return request }
    
    switch provider.method {
    case "GET":
      var components = URLComponents(url: provider.url, resolvingAgainstBaseURL: false)
      components?.percentEncodedQueryItems = buildQueryItems(from: parameters)
      if let urlWithParameters = components?.url {
        request.url = urlWithParameters
      }
      
    default:
      switch provider.contentType {
      case .formURLEncoded:
        let bodyString = parameters.compactMap { key, value -> String? in
          guard let value else { return nil }
          let encodedKey = key.percentEncoded
          let encodedValue = "\(value)".percentEncoded
          return "\(encodedKey)=\(encodedValue)"
        }.joined(separator: "&")
        request.httpBody = bodyString.data(using: .utf8)
        
      case .json:
        request.httpBody = try parameters.jsonData()
      }
    }
    
    return request
  }
  
  private func makeDescriptiveDecodingError<T>(_ error: DecodingError, type: T.Type) -> AnError {
    switch error {
    case .typeMismatch(let type, let context):
      return AnError("Decoding error: Type mismatch for \(type) – \(context.debugDescription)")
      
    case .valueNotFound(let value, let context):
      return AnError("Decoding error: Value '\(value)' not found – \(context.debugDescription)")
      
    case .keyNotFound(let key, let context):
      return AnError("Decoding error: Missing key '\(key.stringValue)' – \(context.debugDescription)")
      
    case .dataCorrupted(let context):
      return AnError("Decoding error: Data corrupted – \(context.debugDescription)")
      
    @unknown default:
      return AnError("Decoding error: Unknown issue decoding \(T.self)")
    }
  }
  
  private func buildQueryItems(from parameters: [String: Any?]) -> [URLQueryItem] {
    parameters.flatMap { key, value -> [URLQueryItem] in
      if let array = value as? [Any?] {
        return array.map { URLQueryItem(name: key, value: $0.map { "\($0)".percentEncoded }) }
      } else {
        return [URLQueryItem(name: key, value: value.map { "\($0)".percentEncoded })]
      }
    }
  }
}
