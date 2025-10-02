//
//  AnEmptyStateView+Preview.swift
//  A360Scribe
//
//  Created by Mike Grankin on 19.03.2025.
//  Copyright © 2025 Aesthetics360. All rights reserved.
//

#if DEBUG
import SwiftUI

struct AnEmptyStateView_Previews: PreviewProvider {
  static var previews: some View {
    UIViewPreview {
      let view = AnEmptyStateView()
      view.titleText = "No Data"
      view.subtitleText = "Please tap {subtitleInlineIcon} to start recording"
      view.titleIconName = "waveform"
      view.inlineIconName = "mic.circle"
      
      view.subtitleInlineIconColor = .systemBlue
      view.subtitleInlineIconSize = 24.0
      view.titleIconColor = .systemBlue
      
      return view
    }
    .previewLayout(.sizeThatFits)
    .padding()
  }
}
#endif
