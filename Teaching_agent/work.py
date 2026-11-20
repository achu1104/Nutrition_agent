import json
import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from groq import Groq

load_dotenv(Path(__file__).resolve().parent / '.env')

TEACHER_PROMPT = '''You are a patient, beginner-friendly Python programming tutor.
Explain concepts in simple language, define jargon, and use short accurate Python examples.
Teach variables, data types, conditions, loops, functions, and other beginner Python topics.
Adapt to the student's question and apparent level. Break difficult ideas into steps.
For conceptual questions, explain the idea, show a runnable example, and describe its output.
For homework or debugging, guide the student with hints and reasoning rather than immediately giving the complete solution, unless they explicitly ask for it.
Finish with one short practice question when appropriate.
If a question is unrelated to Python, politely redirect to Python learning.
Never pretend you executed code.'''

JUDGE_PROMPT = '''You are an independent evaluator of a beginner Python tutor.
Evaluate the tutor's answer to the student's actual question, not the tutor's intentions.
Score each criterion with an integer from 0 (poor) to 5 (excellent):
conceptual_accuracy: correct Python concepts and code
clarity: easy-to-follow explanation
beginner_friendliness: accessible to beginners
example_quality: relevant, correct, useful examples (score fairly if no example is needed)
teaching_approach: guidance, scaffolding, and learning reinforcement
Be critical but fair. Return only one JSON object with exactly these keys:
conceptual_accuracy, clarity, beginner_friendliness, example_quality,
teaching_approach, total_score, feedback, suggestions.
The five criterion fields must be integers 0 through 5.
total_score must equal their sum (0 through 25).
feedback and suggestions must be concise strings. No markdown fences.'''

SCORE_KEYS = [
    'conceptual_accuracy', 'clarity', 'beginner_friendliness',
    'example_quality', 'teaching_approach'
]


def ask_teacher(client: Groq, question: str, history: list) -> str:
    messages = [{'role': 'system', 'content': TEACHER_PROMPT}]
    messages.extend(history[-10:])
    messages.append({'role': 'user', 'content': question})
    result = client.chat.completions.create(
        model='llama-3.3-70b-versatile', messages=messages, temperature=0.4
    )
    answer = result.choices[0].message.content
    if not answer:
        raise ValueError('Teaching model returned an empty answer')
    return answer


def evaluate(client: Groq, question: str, answer: str) -> dict:
    result = client.chat.completions.create(
        model='llama-3.3-70b-versatile',
        messages=[
            {'role': 'system', 'content': JUDGE_PROMPT},
            {'role': 'user', 'content': json.dumps({
                'student_question': question, 'teaching_response': answer
            })},
        ],
        response_format={'type': 'json_object'},
        temperature=0,
    )
    raw = result.choices[0].message.content
    data = json.loads(raw)
    for key in SCORE_KEYS:
        value = data.get(key)
        if type(value) is not int or not 0 <= value <= 5:
            raise ValueError(f'Invalid score for {key}: {value!r}')
    for key in ('feedback', 'suggestions'):
        if not isinstance(data.get(key), str):
            raise ValueError(f'Invalid {key}')
    # Compute total locally so it always matches the individual scores.
    data['total_score'] = sum(data[key] for key in SCORE_KEYS)
    return {key: data[key] for key in [*SCORE_KEYS, 'total_score', 'feedback', 'suggestions']}


st.set_page_config(page_title='Python Teaching Agent + LLM Judge', page_icon='🐍', layout='wide')
st.title('🐍 Python Teaching Agent with LLM Judge')
st.caption('Learn beginner Python and see how an independent LLM evaluates each answer.')

api_key = os.getenv('GROQ_API_KEY')
if not api_key:
    st.error('Missing GROQ_API_KEY. Add it to the .env file and restart Streamlit.')
    st.stop()
client = Groq(api_key=api_key)

if 'interactions' not in st.session_state:
    st.session_state.interactions = []
if 'history' not in st.session_state:
    st.session_state.history = []

with st.sidebar:
    st.header('Try these topics')
    st.write('Variables • Data types • If/else • For/while loops • Functions')
    if st.button('Clear conversation'):
        st.session_state.interactions = []
        st.session_state.history = []
        st.rerun()

with st.form('question_form', clear_on_submit=True):
    question = st.text_input('Ask a Python question', placeholder='What is a Python variable?')
    submitted = st.form_submit_button('Teach me and evaluate')

if submitted:
    if not question.strip():
        st.warning('Please enter a question.')
    else:
        try:
            with st.spinner('Teaching agent is preparing an explanation...'):
                answer = ask_teacher(client, question.strip(), st.session_state.history)
            # Keep context for future teaching even if evaluation fails.
            st.session_state.history.extend([
                {'role': 'user', 'content': question.strip()},
                {'role': 'assistant', 'content': answer},
            ])
            score = None
            judge_error = None
            try:
                with st.spinner('Independent LLM judge is evaluating...'):
                    score = evaluate(client, question.strip(), answer)
            except Exception as exc:
                judge_error = str(exc)
            st.session_state.interactions.append({
                'question': question.strip(), 'answer': answer,
                'evaluation': score, 'judge_error': judge_error,
            })
        except Exception as exc:
            st.error(f'Teaching request failed: {exc}')

for index, item in enumerate(reversed(st.session_state.interactions), start=1):
    st.divider()
    st.subheader(f'Question: {item["question"]}')
    left, right = st.columns([3, 2])
    with left:
        st.markdown('#### 👩‍🏫 Teaching Agent')
        st.markdown(item['answer'])
    with right:
        st.markdown('#### ⚖️ LLM Judge')
        evaluation = item['evaluation']
        if evaluation is None:
            st.warning('Judge evaluation failed; no score is available.')
            st.caption(item['judge_error'] or 'Unknown evaluation error')
        else:
            st.metric('Total score', f'{evaluation["total_score"]}/25')
            for key in SCORE_KEYS:
                st.write(f'{key.replace("_", " ").title()}: {evaluation[key]}/5')
                st.progress(evaluation[key] / 5)
            st.write('**Feedback:**', evaluation['feedback'])
            st.write('**Suggestions:**', evaluation['suggestions'])
            with st.expander('Structured JSON evaluation'):
                st.json(evaluation)

if st.session_state.interactions:
    report = [
        {'question': i['question'], 'teaching_response': i['answer'],
         'evaluation': i['evaluation'], 'judge_error': i['judge_error']}
        for i in st.session_state.interactions
    ]
    st.download_button('Download evaluation report (JSON)',
                       data=json.dumps(report, indent=2),
                       file_name='teaching_evaluations.json',
                       mime='application/json')
