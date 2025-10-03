import streamlit as st
import pandas as pd
import json
import time
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
from utils.supabase_client import supabase, db_client

st.set_page_config(page_title="A360 Prompt Testing", layout="wide")

# Check authentication
if "user" not in st.session_state or st.session_state["user"] is None:
    st.error("🔒 Please login to access the Prompt Testing tool")
    st.stop()

st.title("🧪 A360 Prompt Testing Laboratory")
st.markdown("Test and evaluate prompts across different agents and models")

# Sidebar for test configuration
st.sidebar.header("🔧 Test Configuration")

# Agent/Model Selection
agent_options = [
    "A360 GenAI Agent",
    "DataSync Agent", 
    "ContentCrawl Agent",
    "MariaDB Query Agent",
    "N8N Workflow Agent",
    "OpenAI GPT-4",
    "Claude 3.5 Sonnet",
    "Custom Agent"
]

selected_agent = st.sidebar.selectbox("Select Agent/Model", agent_options)

# Test Mode Selection
test_mode = st.sidebar.radio(
    "Test Mode",
    ["Single Prompt", "Batch Testing", "A/B Comparison", "Performance Benchmarking"]
)

# Main content area
if test_mode == "Single Prompt":
    st.header("🎯 Single Prompt Testing")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Input")
        
        # Prompt input
        prompt_text = st.text_area(
            "Enter your prompt:",
            height=200,
            placeholder="Type your prompt here..."
        )
        
        # Additional parameters
        with st.expander("⚙️ Advanced Parameters"):
            temperature = st.slider("Temperature", 0.0, 2.0, 0.7, 0.1)
            max_tokens = st.number_input("Max Tokens", 1, 4000, 1000)
            top_p = st.slider("Top P", 0.0, 1.0, 1.0, 0.05)
        
        # Test button
        if st.button("🚀 Run Test", type="primary"):
            if prompt_text.strip():
                with st.spinner(f"Testing with {selected_agent}..."):
                    # Simulate API call (replace with actual agent/API integration)
                    time.sleep(2)  # Simulate processing time
                    
                    # Mock response data
                    response_data = {
                        "response": f"This is a sample response from {selected_agent} to your prompt about: {prompt_text[:100]}...",
                        "tokens_used": 150,
                        "response_time": 1.23,
                        "cost": 0.003,
                        "model_version": "v2.1",
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    # Store in session state for display
                    st.session_state["last_test_result"] = response_data
                    
                    # Log to Supabase if available
                    try:
                        log_data = {
                            "user_email": st.session_state["user"],
                            "agent_model": selected_agent,
                            "prompt": prompt_text,
                            "response": response_data["response"],
                            "tokens_used": response_data["tokens_used"],
                            "response_time": response_data["response_time"],
                            "cost": response_data["cost"],
                            "parameters": {
                                "temperature": temperature,
                                "max_tokens": max_tokens,
                                "top_p": top_p
                            }
                        }
                        
                        supabase.table("prompt_tests").insert(log_data).execute()
                        
                    except Exception as e:
                        st.warning(f"Could not log to database: {e}")
            else:
                st.error("Please enter a prompt to test")
    
    with col2:
        st.subheader("Results")
        
        if "last_test_result" in st.session_state:
            result = st.session_state["last_test_result"]
            
            # Response
            st.markdown("**Response:**")
            st.text_area("", value=result["response"], height=200, disabled=True)
            
            # Metrics
            col2a, col2b, col2c = st.columns(3)
            with col2a:
                st.metric("Tokens Used", result["tokens_used"])
            with col2b:
                st.metric("Response Time", f"{result['response_time']}s")
            with col2c:
                st.metric("Cost", f"${result['cost']:.4f}")
            
            # Additional details
            with st.expander("📊 Test Details"):
                st.json(result)
            
            # Rating system
            st.markdown("**Rate this response:**")
            rating = st.radio(
                "Quality Rating:",
                ["⭐ Poor", "⭐⭐ Fair", "⭐⭐⭐ Good", "⭐⭐⭐⭐ Great", "⭐⭐⭐⭐⭐ Excellent"],
                horizontal=True
            )
            
            if st.button("💾 Save Rating"):
                st.success("Rating saved!")
        else:
            st.info("Run a test to see results here")

elif test_mode == "Batch Testing":
    st.header("📊 Batch Testing")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Test Dataset")
        
        # Upload CSV option
        uploaded_file = st.file_uploader("Upload CSV with prompts", type=['csv'])
        
        if uploaded_file:
            df = pd.read_csv(uploaded_file)
            st.dataframe(df.head())
            
            if st.button("🔄 Run Batch Test"):
                progress_bar = st.progress(0)
                results = []
                
                for i, row in df.iterrows():
                    progress_bar.progress((i + 1) / len(df))
                    
                    # Simulate batch processing
                    time.sleep(0.5)
                    
                    # Mock results
                    result = {
                        "prompt": row.get("prompt", ""),
                        "response": f"Batch response {i+1}",
                        "tokens": 100 + i * 10,
                        "response_time": 1.0 + (i * 0.1),
                        "cost": 0.002 + (i * 0.001)
                    }
                    results.append(result)
                
                st.session_state["batch_results"] = results
                st.success(f"Completed {len(results)} tests!")
        
        else:
            # Sample prompts
            sample_prompts = [
                "Explain quantum computing in simple terms",
                "Write a marketing email for a SaaS product",
                "Create a Python function to sort a list",
                "Summarize the benefits of renewable energy"
            ]
            
            st.markdown("**Or use sample prompts:**")
            if st.button("🎲 Use Sample Dataset"):
                st.session_state["batch_results"] = [
                    {
                        "prompt": prompt,
                        "response": f"Sample response to: {prompt}",
                        "tokens": 120,
                        "response_time": 1.5,
                        "cost": 0.003
                    } for prompt in sample_prompts
                ]
    
    with col2:
        if "batch_results" in st.session_state:
            st.subheader("📈 Batch Results")
            
            results_df = pd.DataFrame(st.session_state["batch_results"])
            
            # Summary metrics
            col2a, col2b, col2c, col2d = st.columns(4)
            with col2a:
                st.metric("Total Tests", len(results_df))
            with col2b:
                st.metric("Avg Tokens", f"{results_df['tokens'].mean():.0f}")
            with col2c:
                st.metric("Avg Time", f"{results_df['response_time'].mean():.2f}s")
            with col2d:
                st.metric("Total Cost", f"${results_df['cost'].sum():.4f}")
            
            # Charts
            fig_tokens = px.bar(results_df, y="tokens", title="Tokens Used per Test")
            st.plotly_chart(fig_tokens, use_container_width=True)
            
            fig_time = px.line(results_df, y="response_time", title="Response Time Trend")
            st.plotly_chart(fig_time, use_container_width=True)
            
            # Detailed results
            st.dataframe(results_df)

elif test_mode == "A/B Comparison":
    st.header("⚖️ A/B Model Comparison")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Model A")
        model_a = st.selectbox("Select Model A", agent_options, key="model_a")
        
    with col2:
        st.subheader("Model B") 
        model_b = st.selectbox("Select Model B", agent_options, key="model_b", index=1)
    
    # Comparison prompt
    comparison_prompt = st.text_area(
        "Enter prompt to test both models:",
        height=150,
        placeholder="Enter a prompt that will be tested on both models..."
    )
    
    if st.button("🆚 Compare Models"):
        if comparison_prompt.strip():
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown(f"**{model_a} Response:**")
                with st.spinner("Testing Model A..."):
                    time.sleep(1.5)
                    response_a = f"Response from {model_a}: This is how I would handle the prompt about {comparison_prompt[:50]}..."
                    st.text_area("", value=response_a, height=200, disabled=True, key="resp_a")
                
                # Metrics for Model A
                col1a, col1b = st.columns(2)
                with col1a:
                    st.metric("Tokens", 145)
                    st.metric("Time", "1.2s")
                with col1b:
                    st.metric("Cost", "$0.003")
                    st.metric("Quality", "8.5/10")
            
            with col2:
                st.markdown(f"**{model_b} Response:**")
                with st.spinner("Testing Model B..."):
                    time.sleep(1.8)
                    response_b = f"Response from {model_b}: Here's my take on the prompt regarding {comparison_prompt[:50]}..."
                    st.text_area("", value=response_b, height=200, disabled=True, key="resp_b")
                
                # Metrics for Model B
                col2a, col2b = st.columns(2)
                with col2a:
                    st.metric("Tokens", 160)
                    st.metric("Time", "1.8s")
                with col2b:
                    st.metric("Cost", "$0.004")
                    st.metric("Quality", "8.2/10")
            
            # Comparison summary
            st.markdown("---")
            st.subheader("📊 Comparison Summary")
            
            comparison_data = {
                "Model": [model_a, model_b],
                "Tokens": [145, 160],
                "Time (s)": [1.2, 1.8],
                "Cost ($)": [0.003, 0.004],
                "Quality": [8.5, 8.2]
            }
            
            comparison_df = pd.DataFrame(comparison_data)
            st.dataframe(comparison_df, use_container_width=True)
            
            # Winner selection
            st.markdown("**Which response is better?**")
            winner = st.radio(
                "Vote for the better response:",
                [f"{model_a}", f"{model_b}", "Tie"],
                horizontal=True
            )
            
            if st.button("🗳️ Submit Vote"):
                st.success(f"Vote recorded: {winner}")

elif test_mode == "Performance Benchmarking":
    st.header("🏆 Performance Benchmarking")
    
    # Benchmark configuration
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Benchmark Setup")
        
        benchmark_type = st.selectbox(
            "Benchmark Type",
            ["Response Quality", "Speed Test", "Cost Analysis", "Accuracy Test"]
        )
        
        num_tests = st.slider("Number of test runs", 5, 100, 20)
        
        models_to_test = st.multiselect(
            "Models to benchmark",
            agent_options,
            default=agent_options[:3]
        )
    
    with col2:
        st.subheader("Test Scenarios")
        
        scenarios = st.text_area(
            "Test scenarios (one per line):",
            value="Summarize a technical document\nWrite creative content\nAnswer factual questions\nSolve math problems",
            height=150
        )
    
    if st.button("🚀 Run Benchmark"):
        if models_to_test and scenarios.strip():
            scenario_list = [s.strip() for s in scenarios.split('\n') if s.strip()]
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Simulate benchmark running
            benchmark_results = []
            total_tests = len(models_to_test) * len(scenario_list) * num_tests
            current_test = 0
            
            for model in models_to_test:
                for scenario in scenario_list:
                    for test_run in range(num_tests):
                        current_test += 1
                        progress_bar.progress(current_test / total_tests)
                        status_text.text(f"Testing {model} on scenario: {scenario[:30]}...")
                        
                        time.sleep(0.1)  # Simulate test time
                        
                        # Mock benchmark data
                        result = {
                            "model": model,
                            "scenario": scenario,
                            "run": test_run + 1,
                            "response_time": 1.0 + (test_run * 0.1),
                            "tokens": 100 + (test_run * 5),
                            "cost": 0.002 + (test_run * 0.0001),
                            "quality_score": 7.0 + (test_run * 0.1)
                        }
                        benchmark_results.append(result)
            
            st.session_state["benchmark_results"] = benchmark_results
            status_text.text("Benchmark completed!")
            progress_bar.progress(1.0)
    
    # Display benchmark results
    if "benchmark_results" in st.session_state:
        st.markdown("---")
        st.subheader("📊 Benchmark Results")
        
        results_df = pd.DataFrame(st.session_state["benchmark_results"])
        
        # Summary by model
        summary = results_df.groupby("model").agg({
            "response_time": "mean",
            "tokens": "mean", 
            "cost": "mean",
            "quality_score": "mean"
        }).round(3)
        
        st.dataframe(summary, use_container_width=True)
        
        # Visualizations
        col1, col2 = st.columns(2)
        
        with col1:
            fig_time = px.box(results_df, x="model", y="response_time", 
                             title="Response Time Distribution")
            st.plotly_chart(fig_time, use_container_width=True)
        
        with col2:
            fig_quality = px.box(results_df, x="model", y="quality_score",
                               title="Quality Score Distribution") 
            st.plotly_chart(fig_quality, use_container_width=True)
        
        # Export results
        if st.button("📥 Export Results"):
            csv = results_df.to_csv(index=False)
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name=f"benchmark_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )

# Footer with test history
st.markdown("---")
st.subheader("📝 Recent Test History")

# Mock recent tests (replace with Supabase query)
recent_tests = [
    {"timestamp": "2024-10-03 15:30", "agent": "A360 GenAI Agent", "type": "Single", "status": "✅"},
    {"timestamp": "2024-10-03 14:45", "agent": "Claude 3.5", "type": "Batch", "status": "✅"},
    {"timestamp": "2024-10-03 13:20", "agent": "Multiple", "type": "A/B Test", "status": "✅"},
    {"timestamp": "2024-10-03 12:15", "agent": "Multiple", "type": "Benchmark", "status": "⏳"},
]

history_df = pd.DataFrame(recent_tests)
st.dataframe(history_df, use_container_width=True)