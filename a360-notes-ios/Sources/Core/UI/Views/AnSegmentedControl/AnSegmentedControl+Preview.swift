//
//  AnSegmentedControl+Preview.swift
//  A360Scribe
//
//  Created by Mike Grankin on 19.03.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

#if DEBUG
import SwiftUI

struct AnSegmentedControl_Previews: PreviewProvider {
  static var previews: some View {
    UIViewPreview {
      let segmentedControl = AnSegmentedControl(frame: CGRect(x: 0.0, y: 0.0, width: 300.0, height: 44.0))
      segmentedControl.itemTitles = "First, Second, Third"
      segmentedControl.itemIconNames = "star, bell, gear"
      segmentedControl.selectedColor = .systemBlue
      segmentedControl.unselectedColor = .systemGray
      segmentedControl.underlineHeight = 2.0
      segmentedControl.selectSegment(at: 0, animated: false)
      
      return segmentedControl
    }
    .previewLayout(.sizeThatFits)
    .padding()
  }
}
#endif
