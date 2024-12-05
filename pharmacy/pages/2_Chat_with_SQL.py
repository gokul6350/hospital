import streamlit as st
import sqlite3
import google.generativeai as genai
from threading import Lock

def remove_sql_markers(text):
    if text.startswith("```sql"):
        text = text.replace("```sql", "")
        text = text.replace("\n```", "")
        return text.strip()
    else:
        return text

class HospitalDatabaseQA:
    def __init__(self, db_path="instance/hospital.db"):
        # Setup SQLite with check_same_thread=False
        self.db_path = db_path
        self.lock = Lock()
        
    def get_connection(self):
        return sqlite3.connect(self.db_path, check_same_thread=False)
        
    def _get_database_schema(self):
        with self.lock:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            
            schema = []
            for table in tables:
                table_name = table[0]
                cursor.execute(f"PRAGMA table_info({table_name});")
                columns = cursor.fetchall()
                schema.append(f"Table {table_name}:")
                for col in columns:
                    schema.append(f"  - {col[1]} ({col[2]})")
            
            conn.close()
            return "\n".join(schema)

    def ask(self, question):
        try:
            # Setup Gemini for each request
            genai.configure(api_key="AIzaSyBoUqeC-oQDQQWMe5-Vcmd17RoGw8qqZVM")
            model = genai.GenerativeModel(
                model_name="gemini-1.5-flash",
                generation_config={
                    "temperature": 0.1,
                    "top_p": 0.95,
                    "top_k": 40,
                    "max_output_tokens": 8192,
                }
            )

            # Get schema
            schema = self._get_database_schema()
            
            # Generate SQL query
            prompt = f"""
            Given the following SQLite database schema:
            {schema}

            Generate a SQL query to answer this question: {question}
            Return ONLY the SQL query, without any explanations.
            """
            
            response = model.generate_content(prompt)
            sql_query = remove_sql_markers(response.text.strip())
            
            print("\n==============")
            print(f"User Input: {question}")
            print(f"Generated SQL Query: {sql_query}")
            
            # Execute query with new connection
            with self.lock:
                conn = self.get_connection()
                cursor = conn.cursor()
                cursor.execute(sql_query)
                results = cursor.fetchall()
                
                print("Query Results (first 4 rows):")
                for row in results[:4]:
                    print(row)
                
                conn.close()
            
            # Format response
            #formatted_data = results[0][0] if results and len(results) > 0 else 0
            formatted_data = results
            prompt = f"""
            Question: {question}
            Raw data from database: The query returned {formatted_data}
            
            Please provide a natural, helpful response to the question using this exact number.
            Make sure to use the exact number from the data in your response.
            """
            print("==============")
            print(prompt)
            print("==============")
            response = model.generate_content(prompt)
            print(f"Gemini Response: {response.text.strip()}")
            print("==============\n")
            
            return response.text.strip()
            
        except sqlite3.Error as e:
            print(f"\n==============\nDatabase Error: {e}\n==============\n")
            return f"Database error: {e}"
        except Exception as e:
            print(f"\n==============\nError: {e}\n==============\n")
            return f"Error: {e}"

    def format_response(self, question, data):
        # Convert tuple data to a more readable format
        if data:
            formatted_data = ", ".join(row[0] for row in data)
        else:
            formatted_data = "no tables found"
        
        prompt = f"""
        Question: {question}
        Raw data from database: The query returned the following tables: {formatted_data}
        
        Please provide a natural, helpful response to the question using this exact information.
        """
        print("==============")
        print(prompt)
        print("==============")
        response = self.model.generate_content(prompt)

        return response.text.strip()

def chat_interface():
    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    # Add clear chat button to sidebar
    with st.sidebar:
        if st.button("Clear Chat History"):
            st.session_state.messages = []
            st.rerun()

    # Add custom CSS for chat container
    st.markdown("""
        <style>
            [data-testid="stChatMessageContainer"] {
                max-height: 400px;
                overflow-y: auto;
            }
        </style>
    """, unsafe_allow_html=True)

    # Initialize QA system for each session
    if "qa_system" not in st.session_state:
        st.session_state.qa_system = HospitalDatabaseQA()

    # Display chat messages from history on app rerun
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Accept user input
    if prompt := st.chat_input("Ask about the database..."):
        # Create a new QA system instance for each query
        qa_system = HospitalDatabaseQA()
        
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)

        # Generate and display assistant response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = qa_system.ask(prompt)
            st.markdown(response)
            
        # Add assistant response to chat history
        st.session_state.messages.append({"role": "assistant", "content": response})

def main():
    st.title("Chat with SQL Database")
    chat_interface()

if __name__ == "__main__":
    main()
