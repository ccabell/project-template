import streamlit as st

st.title("A360 Quick Prompt Tester")

prompt = st.text_area("Enter your prompt")

if st.button("Submit"):
    st.write("Processing:", prompt)
    # later you can send this to Supabase/Warp

def upload_transcript_tab():
    """Upload transcript functionality"""
    st.header("Upload New Transcript")
    
    # File uploader
    uploaded_file = st.file_uploader(
        "Choose a transcript file",
        type=['txt', 'docx', 'pdf'],
        help="Supported formats: TXT, DOCX, PDF (max 10MB)"
    )
    
    # Description input
    description = st.text_area("Description (optional)", placeholder="Enter a description for this transcript...")
    
    if uploaded_file is not None:
        # Validate file size
        size_valid, size_error = validate_file_size(uploaded_file, max_size_mb=10)
        if not size_valid:
            st.error(size_error)
            return
        
        # File information
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("File Name", uploaded_file.name)
        with col2:
            st.metric("File Size", f"{uploaded_file.size / 1024:.1f} KB")
        with col3:
            st.metric("File Type", uploaded_file.type)
        
        # Process file
        with st.spinner("Processing file..."):
            content, error = process_uploaded_file(uploaded_file)
        
        if error:
            st.error(f"Error: {error}")
            return
        
        # Show preview
        st.subheader("Content Preview")
        preview = get_file_preview(content, 1000)
        st.text_area("Preview", preview, height=200, disabled=True)
        
        # Save button
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("💾 Save Transcript", type="primary"):
                with st.spinner("Saving transcript..."):
                    transcript_id = save_transcript(uploaded_file.name, content, description)
                    st.success(f"✅ Transcript saved successfully! ID: {transcript_id}")
                    time.sleep(1)
                    st.rerun()

def test_prompts_tab():
    """Test prompts functionality"""
    st.header("Test Prompts Against Transcripts")
    
    # Get all transcripts
    transcripts = get_all_transcripts()
    
    if not transcripts:
        st.warning("No transcripts available. Please upload some transcripts first.")
        return
    
    # Transcript selection
    transcript_options = {f"{t['filename']} (ID: {t['id']})": t['id'] for t in transcripts}
    selected_transcript_key = st.selectbox("Select Transcript", list(transcript_options.keys()))
    selected_transcript_id = transcript_options[selected_transcript_key]
    
    # Show transcript details
    selected_transcript = next(t for t in transcripts if t['id'] == selected_transcript_id)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Words", selected_transcript['word_count'])
    with col2:
        st.metric("Size", f"{selected_transcript['file_size']} bytes")
    with col3:
        st.metric("Uploaded", selected_transcript['upload_date'][:10])
    
    # Model selection (if OpenAI configured)
    if st.session_state.openai_configured:
        models = get_available_models()
        selected_model = st.selectbox("AI Model", models, index=0 if 'gpt-3.5-turbo' in models else 0)
    else:
        st.info("💡 Configure OpenAI API key in the sidebar to use real AI models")
        selected_model = "mock"
    
    # Prompt input
    st.subheader("Enter Your Prompt")
    
    # Predefined prompts
    predefined_prompts = [
        "Custom prompt...",
        "Summarize this transcript in 3-5 bullet points",
        "What are the main topics discussed in this transcript?",
        "Identify any action items or decisions made",
        "What questions were asked in this transcript?",
        "Extract all names and entities mentioned",
        "What is the overall sentiment of this conversation?",
        "List any problems or issues discussed"
    ]
    
    selected_prompt_template = st.selectbox("Use a template or write custom:", predefined_prompts)
    
    if selected_prompt_template == "Custom prompt...":
        prompt = st.text_area("Your prompt:", height=100, placeholder="Enter your analysis prompt here...")
    else:
        prompt = st.text_area("Your prompt:", value=selected_prompt_template, height=100)
    
    # Run prompt button
    if st.button("🚀 Run Analysis", type="primary", disabled=not prompt.strip()):
        if not prompt.strip():
            st.error("Please enter a prompt")
            return
        
        # Get transcript content
        transcript_content = get_transcript_content(selected_transcript_id)
        if not transcript_content:
            st.error("Could not retrieve transcript content")
            return
        
        # Show progress
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        status_text.text("Processing prompt...")
        progress_bar.progress(25)
        
        # Process with AI or mock
        if st.session_state.openai_configured:
            status_text.text("Sending to AI model...")
            progress_bar.progress(50)
            result, error = process_prompt_with_openai(transcript_content, prompt, selected_model)
        else:
            status_text.text("Generating mock response...")
            progress_bar.progress(50)
            result, error = process_prompt_mock(transcript_content, prompt)
        
        progress_bar.progress(75)
        
        if error:
            progress_bar.empty()
            status_text.empty()
            st.error(f"Error: {error}")
            return
        
        # Save result
        status_text.text("Saving result...")
        progress_bar.progress(90)
        result_id = save_prompt_result(selected_transcript_id, prompt, result)
        
        progress_bar.progress(100)
        status_text.text("Complete!")
        time.sleep(0.5)
        
        progress_bar.empty()
        status_text.empty()
        
        # Display result
        st.subheader("📋 Analysis Result")
        st.markdown(result)
        
        # Copy button
        st.code(result)
        
        st.success(f"✅ Analysis complete! Result saved with ID: {result_id}")

def manage_transcripts_tab():
    """Manage transcripts functionality"""
    st.header("Manage Transcripts")
    
    # Get all transcripts
    transcripts = get_all_transcripts()
    
    if not transcripts:
        st.info("No transcripts found. Upload some transcripts to get started.")
        return
    
    # Create DataFrame for display
    df_data = []
    for t in transcripts:
        df_data.append({
            'ID': t['id'],
            'Filename': t['filename'],
            'Description': t['description'][:50] + "..." if len(t.get('description', '')) > 50 else t.get('description', ''),
            'Words': t['word_count'],
            'Size (bytes)': t['file_size'],
            'Upload Date': t['upload_date'][:16]
        })
    
    df = pd.DataFrame(df_data)
    
    # Display table
    st.dataframe(df, use_container_width=True)
    
    # Actions
    st.subheader("Actions")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # View transcript
        transcript_to_view = st.selectbox("View transcript content:", 
                                        [f"{t['filename']} (ID: {t['id']})" for t in transcripts])
        
        if st.button("👁️ View Content"):
            transcript_id = int(transcript_to_view.split("ID: ")[1].split(")")[0])
            content = get_transcript_content(transcript_id)
            if content:
                st.subheader(f"Content: {transcript_to_view}")
                st.text_area("Transcript Content", content, height=400, disabled=True)
            else:
                st.error("Could not retrieve transcript content")
    
    with col2:
        # Delete transcript
        transcript_to_delete = st.selectbox("Delete transcript:", 
                                          [f"{t['filename']} (ID: {t['id']})" for t in transcripts])
        
        if st.button("🗑️ Delete Transcript", type="secondary"):
            transcript_id = int(transcript_to_delete.split("ID: ")[1].split(")")[0])
            
            # Confirmation
            if st.button(f"⚠️ Confirm Delete: {transcript_to_delete}", type="secondary"):
                if delete_transcript(transcript_id):
                    st.success("✅ Transcript deleted successfully!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ Error deleting transcript")

if __name__ == "__main__":
    main()