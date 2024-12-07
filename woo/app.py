from flask import Flask, render_template, request, jsonify
from chat import HospitalDatabaseQA

app = Flask(__name__)
qa_system = HospitalDatabaseQA()

@app.route('/')
def home():
    return render_template('chat.html')

@app.route('/api/query', methods=['POST'])
def query():
    try:
        question = request.json.get('message')
        answer = qa_system.ask(question)
        return jsonify({'response': answer})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)