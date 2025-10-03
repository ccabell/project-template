# 📝 Transcript Prompt Tester

A Streamlit-based application for uploading transcripts and testing AI prompts against them. Perfect for analyzing meeting transcripts, interviews, calls, and other text content.

## 🚀 Features

- **File Upload**: Support for TXT, DOCX, and PDF files
- **AI Integration**: OpenAI GPT models for intelligent analysis (with mock fallback)
- **Prompt Templates**: Pre-built prompts for common analysis tasks
- **Database Storage**: SQLite database for transcript and result storage
- **Recent Activity**: Track your recent prompt tests
- **Content Management**: View and delete stored transcripts

## 📋 Requirements

- Python 3.7+
- Streamlit
- OpenAI API (optional, falls back to mock responses)
- SQLite (built-in with Python)

## 🛠️ Installation

The required packages should already be installed. If not:
```bash
pip install streamlit python-docx PyPDF2 openai pandas
```

## 🎯 Usage

1. **Start the application**:
   ```bash
   python -m streamlit run streamlit_app.py
   ```

2. **Configure OpenAI (Optional)**:
   - Enter your OpenAI API key in the sidebar
   - If no API key is provided, the app will use mock responses

3. **Upload Transcripts**:
   - Go to the "Upload Transcripts" tab
   - Upload TXT, DOCX, or PDF files
   - Add optional descriptions
   - Preview content before saving

4. **Test Prompts**:
   - Go to the "Test Prompts" tab
   - Select a transcript from your uploaded files
   - Choose from predefined prompts or write custom ones
   - Run analysis and view results

5. **Manage Transcripts**:
   - View all uploaded transcripts in a table
   - Preview transcript content
   - Delete transcripts you no longer need

## 📝 Sample Prompts

The application includes several built-in prompt templates:

- **Summarize**: Get key points from the transcript
- **Topics**: Identify main discussion topics
- **Action Items**: Extract decisions and next steps
- **Questions**: Find all questions asked
- **Entities**: Extract names and important entities
- **Sentiment**: Analyze the overall tone
- **Issues**: Identify problems or concerns discussed

## 🗂️ File Structure

```
transcript-tester/
├── streamlit_app.py      # Main Streamlit application
├── database.py           # Database operations
├── file_processors.py    # File upload and processing
├── ai_processor.py       # AI/OpenAI integration
├── sample_transcript.txt # Sample file for testing
├── transcripts.db        # SQLite database (created on first run)
└── TRANSCRIPT_TESTER_README.md # This file
```

## 🧪 Testing

1. Use the included `sample_transcript.txt` to test the upload functionality
2. Try different prompts to see how the analysis works
3. Test with and without OpenAI API key to see both modes

## 🔧 Configuration

### OpenAI Settings
- **API Key**: Enter in the sidebar (stored in session only)
- **Models**: Automatically detects available models
- **Fallback**: Uses mock responses if OpenAI is unavailable

### File Limits
- **Max file size**: 10MB per file
- **Supported formats**: TXT, DOCX, PDF
- **Content preview**: First 1000 characters shown

## 📊 Database Schema

### Transcripts Table
- `id`: Primary key
- `filename`: Original filename
- `content`: Full transcript text
- `upload_date`: When uploaded
- `file_size`: Size in bytes
- `word_count`: Number of words
- `description`: Optional description

### Prompt Results Table
- `id`: Primary key
- `transcript_id`: References transcripts table
- `prompt`: The prompt used
- `result`: AI analysis result
- `timestamp`: When processed

## 🚨 Troubleshooting

### Common Issues

1. **"Module not found" errors**:
   ```bash
   pip install streamlit python-docx PyPDF2 openai pandas
   ```

2. **OpenAI API errors**:
   - Check your API key is valid
   - Ensure you have sufficient credits
   - App will fall back to mock responses if needed

3. **File upload issues**:
   - Check file size (max 10MB)
   - Ensure file format is supported (TXT, DOCX, PDF)
   - Try converting the file to plain text if issues persist

4. **Database errors**:
   - Delete `transcripts.db` file to reset database
   - Restart the application

## 💡 Tips

- Start with the sample transcript to learn the interface
- Use descriptive filenames for your transcripts
- Try different prompt variations to get better results
- The mock responses show transcript statistics when OpenAI isn't configured
- Recent activity in the sidebar shows your last 5 prompt tests

## 🔐 Privacy

- All data is stored locally in SQLite database
- OpenAI API key is only stored in session memory
- No data is sent to external services except OpenAI (if configured)

Happy analyzing! 🎉