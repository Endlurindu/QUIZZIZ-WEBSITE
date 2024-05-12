from flask import Flask, render_template, request, redirect, url_for, flash, session
import firebase_admin
from firebase_admin import credentials
from firebase_admin import db as firebase_db
from firebase_admin import firestore
from uuid import uuid4

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Initialize Firebase Admin SDK
cred = credentials.Certificate("/home/rgukt/my_flask_project/quizziz-2c051-firebase-adminsdk-5mpwp-98c1cc8ce1.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://quizziz-2c051-default-rtdb.firebaseio.com/'
})


# Create a Firestore client
db = firestore.client()

# Routes

# Welcome Route
@app.route('/')
def welcome():
    return render_template('welcome.html')

# Signup Route
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        # Signup logic here
        
        # Assuming signup is successful and user is authenticated
        session['logged_in'] = True  # Set logged_in session variable to True
        
        # Redirect to enter.html after successful signup
        return redirect(url_for('enter'))
    
    return render_template('signup.html')


# Login Route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Login logic here
        
        # Assuming login is successful and user is authenticated
        session['logged_in'] = True  # Set logged_in session variable to True
        
        # Redirect to enter.html after successful login
        return redirect(url_for('enter'))
    
    return render_template('login.html')


# Enter Route (new route for enter.html)
@app.route('/enter')
def enter():
    return render_template('enter.html')


@app.route('/create_quiz', methods=['GET', 'POST'])
def create_quiz():
    if not session.get('logged_in'):
        return redirect(url_for('login'))  # Redirect to login if not logged in
    
    if request.method == 'POST':
        # Generate a unique ID as the default quiz name
        default_quiz_name = '#' + str(uuid4())[:4]  # Restrict to 4 digits and start with '#'
        
        # Extract quiz data from the form
        quiz_name = request.form.get('quiz_name', default_quiz_name)  # Use get() with a default value
        timer = int(request.form['timer'])
        questions = request.form.getlist('questions[]')
        
        # Extract correct options handling NoneType gracefully
        correct_options = [int(request.form.get(f'correct_option_{i}')) if request.form.get(f'correct_option_{i}') is not None else 0 for i in range(1, len(questions) + 1)]

        # Store quiz data in Firebase Realtime Database
        quiz_ref = firebase_db.reference('quizzes')
        new_quiz_ref = quiz_ref.push({
            'name': quiz_name,
            'timer': timer
        })
        quiz_id = new_quiz_ref.key  # Use the Firebase-generated key as the quiz ID

        # Store questions in Firebase Realtime Database
        questions_ref = firebase_db.reference(f'questions/{quiz_id}')
        for i, question in enumerate(questions):
            question_ref = questions_ref.push({
                'question': question
            })
            question_id = question_ref.key

            # Store options separately for each question
            options = request.form.getlist(f'options[{i}][]')
            options_ref = firebase_db.reference(f'options/{quiz_id}/{question_id}')
            for j, option_text in enumerate(options):
                is_correct = 1 if j == correct_options[i] else 0
                options_ref.push({
                    'option_text': option_text,
                    'is_correct': is_correct
                })

        flash('Quiz created successfully!', 'success')
        return redirect(url_for('create_quiz'))
    else:
        return render_template('create_quiz.html')

# Other routes...

@app.route('/join_quiz', methods=['GET', 'POST'])
def join_quiz():
    if not session.get('logged_in'):
        return redirect(url_for('login'))  # Redirect to login if not logged in
    
    if request.method == 'POST':
        quiz_id = request.form.get('quiz_id')
        return redirect(url_for('join_specific_quiz', quiz_id=quiz_id))
    else:
        quizzes_ref = firebase_db.reference('quizzes')
        quizzes = quizzes_ref.get()
        if quizzes is not None:
            quizzes_list = []
            for quiz_id, quiz_data in quizzes.items():
                name = quiz_data.get('name', f'Quiz {quiz_id}')  # Use default name if 'name' field is missing
                duration = quiz_data.get('timer', 'Unknown')  # Get duration or provide a default value
                quizzes_list.append({'id': quiz_id, 'name': name, 'duration': duration})
            return render_template('join_quiz.html', quizzes=quizzes_list)
        else:
            flash('No quizzes available.', 'error')
            return render_template('join_quiz.html', quizzes=[])


@app.route('/join_specific_quiz/<quiz_id>', methods=['GET', 'POST'])
def join_specific_quiz(quiz_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))  # Redirect to login if not logged in

    # Fetch quiz details from Firebase
    quiz_ref = firebase_db.reference(f'quizzes/{quiz_id}')
    quiz_data = quiz_ref.get()
    if quiz_data is None:
        flash('Quiz not found.', 'error')
        return redirect(url_for('join_quiz'))  # Redirect back to join quiz list

    quiz_name = quiz_data['name']
    duration = quiz_data['timer']

    # Fetch questions and options for the quiz from Firebase
    questions_ref = firebase_db.reference(f'questions/{quiz_id}')
    questions_data = questions_ref.get()

    # Check if questions exist
    if questions_data is None:
        flash('No questions available for this quiz.', 'error')
        return render_template('join_specific_quiz.html', quiz_name=quiz_name, duration=duration, quiz_details=[], options={})

    quiz_details = [{'question_id': key, 'question': value['question']} for key, value in questions_data.items()]

    options = {}
    for question_id, question_data in questions_data.items():
        options_ref = firebase_db.reference(f'options/{quiz_id}/{question_id}')
        options_data = options_ref.get()

        # Ensure that options are retrieved correctly
        options[question_id] = []  # Initialize empty list for options
        if options_data:
            options[question_id] = [{'text': option['option_text'], 'is_correct': option['is_correct']} for option in options_data.values()]

    return render_template('join_specific_quiz.html', quiz_name=quiz_name, duration=duration, quiz_details=quiz_details, options=options)


@app.route('/save_quiz_data', methods=['POST'])
def save_quiz_data():
    try:
        # Extract form data
        quiz_name = request.form['quiz_name']
        timer = int(request.form['timer'])
        questions = request.form.getlist('questions[]')
        options = [request.form.getlist(f'options[{question_id}][]') for question_id in questions]
        
        # Extract correct options handling NoneType gracefully
        correct_options = [int(request.form.get(f'correct_option_{i}')) if request.form.get(f'correct_option_{i}') is not None else 0 for i in range(1, len(questions) + 1)]

        # Save quiz data to Firebase
        quiz_ref = firebase_db.reference('quizzes')
        new_quiz_ref = quiz_ref.push({
            'name': quiz_name,
            'timer': timer
        })
        quiz_id = new_quiz_ref.key

        for i, question in enumerate(questions):
            # Save question
            question_ref = firebase_db.reference(f'questions/{quiz_id}')
            new_question_ref = question_ref.push({'question': question})
            question_id = new_question_ref.key

            # Save options
            options_ref = firebase_db.reference(f'options/{quiz_id}/{question_id}')
            for option_text in options[i]:
                options_ref.push({
                    'option_text': option_text
                })

            # Save correct option
            correct_option_ref = firebase_db.reference(f'correct_options/{quiz_id}/{question_id}')
            correct_option_ref.set(correct_options[i])

        flash('Quiz created successfully!', 'success')
        return redirect(url_for('create_quiz'))
    except Exception as e:
        flash(f'Error occurred: {str(e)}', 'error')
        return redirect(url_for('create_quiz'))

@app.route('/submit_quiz', methods=['POST'])
def submit_quiz():
    try:
        # Get the quiz ID from the form data
        quiz_id = request.form['quiz_id']
        
        # Get the username from the session
        username = session.get('username')

        # Get the total number of questions from the database
        questions_ref = firebase_db.reference(f'questions/{quiz_id}')
        questions_data = questions_ref.get()
        total_questions = len(questions_data) if questions_data else 0

        # Initialize counters for correct and incorrect answers
        correct_answers = 0
        incorrect_answers = 0

        # Loop through each question and compare user's answer with correct option
        for question_id in questions_data:
            user_answer = request.form.get(f'answer_{question_id}', None)
            correct_option = get_correct_option_from_database(quiz_id, question_id)  # Pass quiz_id and question_id

            # Check if user's answer matches the correct option
            if user_answer is not None and user_answer == correct_option:
                correct_answers += 1
            else:
                incorrect_answers += 1

        # Calculate the score percentage
        score = (correct_answers / total_questions) * 100

        # Store the user's score along with their username in the Firestore database
        scores_ref = db.collection(f'scores/{quiz_id}')
        scores_ref.add({
            'username': username,
            'score': score
        })

        # Render the score.html template with score details
        return render_template('score.html', total_questions=total_questions, correct_answers=correct_answers, incorrect_answers=incorrect_answers, score=score)

    except Exception as e:
        # Handle any exceptions and redirect to the welcome page
        flash(f'Error occurred: {str(e)}', 'error')
        return redirect(url_for('welcome'))

def get_correct_option_from_database(quiz_id, question_id):
    try:
        # Reference the options for the given quiz and question IDs
        options_ref = firebase_db.reference(f'options/{quiz_id}/{question_id}')
        
        # Get the options data from the database
        options_data = options_ref.get()

        # Iterate through options to find the correct one
        correct_option = None
        if options_data:
            for option_key, option_data in options_data.items():
                if option_data.get('is_correct') == 1:
                    correct_option = option_data.get('option_text')
                    break  # Once correct option is found, exit the loop

        return correct_option

    except Exception as e:
        # Handle any exceptions, such as if the options are not found in the database
        print(f'Error fetching correct option: {e}')
        return None

# Quiz Contact Route
@app.route('/quizz_contact')
def quizz_contact():
    return render_template('quizz_contact.html')

@app.route('/score')
def score():
    try:
        # Fetch scores from Firestore
        scores_ref = db.collection('scores')
        scores = scores_ref.get()

        # Create a list to hold score data
        score_data = []
        for score in scores:
            score_data.append(score.to_dict())  # Convert each score document to a dictionary
        print("Scores:", score_data)  # Debug statement

        # Pass the scores data to the template for rendering
        return render_template('score.html', scores=score_data)

    except Exception as e:
        # Handle any exceptions and redirect to the welcome page
        flash(f'Error occurred: {str(e)}', 'error')
        print("Error:", e)  # Debug statement
        return redirect(url_for('welcome'))

@app.route('/return_to_home')
def return_to_home():
    # Redirect to the welcome page
    return redirect(url_for('welcome'))


if __name__ == '__main__':
    app.run(debug=True)
