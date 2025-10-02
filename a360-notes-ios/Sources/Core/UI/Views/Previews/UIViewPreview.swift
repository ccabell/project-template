//
//  UIViewPreview.swift
//  A360Scribe
//
//  Created by Mike Grankin on 19.03.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

#if DEBUG
import SwiftUI

struct UIViewPreview<View: UIView>: UIViewRepresentable {
  let view: View
  
  init(_ builder: @escaping () -> View) {
    view = builder()
  }
  
  func makeUIView(context: Context) -> UIView {
    view
  }
  
  func updateUIView(_ view: UIView, context: Context) {}
}
#endif
