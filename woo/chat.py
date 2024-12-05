import os
import sqlite3
import google.generativeai as genai

def remove_sql_markers(text):
    # Remove ```sql from the beginning
    if text.startswith("```sql"):
        text = text.replace("```sql", "")
        # Remove ``` from the end
        text = text.replace("\n```", "")
        return text.strip()
    else:
        return text

class HospitalDatabaseQA:
    def __init__(self, db_path="instance/hospital.db"):
        # Setup SQLite
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        
        # Setup Gemini
        genai.configure(api_key="AIzaSyBoUqeC-oQDQQWMe5-Vcmd17RoGw8qqZVM")
        self.model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config={
                "temperature": 0.1,  # Lower temperature for more precise SQL generation
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 8192,
            }
        )

        # Get database schema for context
        self.db_schema = self._get_database_schema()
        
    def _get_database_schema(self):
        # Get all tables and their structures
        self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = self.cursor.fetchall()
        
        schema = []
        for table in tables:
            table_name = table[0]
            self.cursor.execute(f"PRAGMA table_info({table_name});")
            columns = self.cursor.fetchall()
            schema.append(f"Table {table_name}:")
            for col in columns:
                schema.append(f"  - {col[1]} ({col[2]})")
        
        # Print the schema for debugging
        print("\nDatabase Schema sent to Gemini:")
        print("--------------------------------")
        print("\n".join(schema))
        print("--------------------------------\n")
        
        return "\n".join(schema)

    def generate_sql_query(self, question):
        prompt = f"""
        Given the following SQLite database schema:
        {self.db_schema}

        Generate a SQL query to answer this question: {question}
        Return ONLY the SQL query, without any explanations.
        """
        
        response = self.model.generate_content(prompt)
        # Clean the response using the remove_sql_markers function
        query = remove_sql_markers(response.text.strip())
        return query

    def format_response(self, question, data):
        # Convert tuple data to a more readable format
        formatted_data = data[0][0] if data and len(data) > 0 else 0
        
        prompt = f"""
        Question: {question}
        Raw data from database: The query returned {formatted_data}
        
        Please provide a natural, helpful response to the question using this exact number.
        Make sure to use the exact number from the data in your response.
        """
        
        response = self.model.generate_content(prompt)
        return response.text.strip()

    def ask(self, question):
        try:
            # Generate SQL query
            sql_query = self.generate_sql_query(question)
            print(f"Generated SQL: {sql_query}\n")

            # Execute query
            self.cursor.execute(sql_query)
            results = self.cursor.fetchall()

            # Print the first four rows of the results
            print("First 4 rows of SQL response:")
            for row in results[:4]:
                print(row)
            print()

            # Format results using LLM
            answer = self.format_response(question, results)
            return answer

        except sqlite3.Error as e:
            return f"Database error: {e}"
        except Exception as e:
            return f"Error: {e}"

    def __del__(self):
        self.conn.close()

def main():
    qa_system = HospitalDatabaseQA()
    print("Welcome to Hospital Database Q&A (type 'exit' to quit)")
    
    while True:
        question = input("\nAsk a question about the hospital data: ").strip()
        if question.lower() == 'exit':
            break
            
        answer = qa_system.ask(question)
        print("\nAnswer:", answer)

if __name__ == "__main__":
    main()