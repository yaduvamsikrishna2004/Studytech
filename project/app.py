from cachelib import MongoDbCache
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_session import Session
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
from bson import ObjectId
import json

app = Flask(__name__)
app.secret_key = "your_secret_key"

# Configure Flask-Session
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_KEY_PREFIX'] = 'your_prefix:'
Session(app)

# Configure Flask-Mail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'

app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'studytechoffcl@gmail.com'
app.config['MAIL_PASSWORD'] = 'alvclrzfikqxjtct'
app.config['MAIL_DEFAULT_SENDER'] = 'studytechoffcl@gmail.com'
mail = Mail(app)

# Connect to MongoDB
client = MongoClient("mongodb://localhost:27017/")
db = client["StudyTechDB"]
users_collection = db["users"]
contact_collection = db["contact_messages"]
quiz_collection = db['quizzes']  # Collection for quizzes
result_collection = db["results"]  # Collection for quiz results
quiz_results_collection = db["quiz_results"]


ADMIN_EMAIL = "admin@gmail.com"
ADMIN_PASSWORD = generate_password_hash("admin1234")

@app.route('/')
def title_video():
    return render_template('title_video.html', redirect_url=url_for('index'))

@app.route('/index')
def index():
    return render_template('index.html')

@app.route('/services')
def services():
    return render_template('services.html')

@app.route('/contactus', methods=['GET', 'POST'])
def contactus():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        message = request.form.get('message')
        contact_message = {'name': name, 'email': email, 'message': message}
        contact_collection.insert_one(contact_message)
        msg = Message('Contact Form Submission', recipients=[email])
        msg.body = 'Thank you for reaching out! We will get back to you soon.'
        mail.send(msg)
        return jsonify({'status': 'success', 'message': 'Message sent successfully!'})
    return render_template('contactus.html')

@app.route('/signin', methods=['GET', 'POST'])
def signin():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        if email == ADMIN_EMAIL and check_password_hash(ADMIN_PASSWORD, password):
            session['user'] = email
            return redirect(url_for('admin_dashboard'))
        user = users_collection.find_one({"email": email})
        if user and check_password_hash(user['password'], password):
            session['user'] = user['email']
            if not user.get('logged_in', False):
                send_login_email(user['email'], password)
                users_collection.update_one({"email": email}, {"$set": {"logged_in": True}})
            if user.get('form_submitted', False):
                return redirect(url_for('student_dashboard'))
            else:
                return redirect(url_for('submit'))
        return "Invalid credentials. Try again."
    return render_template('signin.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        mobile = request.form['mobile']
        password = request.form['password']
        hashed_password = generate_password_hash(password)
        users_collection.insert_one({
            "name": name,
            "email": email,
            "mobile": mobile,
            "password": hashed_password,
            "logged_in": False,
            "form_submitted": False
        })
        return redirect(url_for('signin'))
    return render_template('signup.html')

@app.route('/admin_dashboard', methods=['GET', 'POST'])
def admin_dashboard():
    if 'user' not in session or session['user'] != ADMIN_EMAIL:
        return redirect(url_for('signin'))

    if request.method == 'POST':
        quiz_type = request.form.get('quiz_type')
        return redirect(url_for('create_regular_quiz')) if quiz_type == 'regular' else redirect(url_for('create_weekend_quiz'))

    return render_template('admin_dashboard.html')

@app.route('/create_regular_quiz', methods=['GET', 'POST'])
def create_regular_quiz():
    if request.method == 'POST':
        quiz_title = request.form['quiz_title']
        quiz_id = request.form['quiz_id']
        questions = []

        # Gather questions from the form data
        question_texts = request.form.getlist('questions[]')
        for i in range(len(question_texts)):
            question = {
                'text': question_texts[i],
                'options': request.form.getlist(f'options[{i}][]'),  # Collect options for each question
                'answer': request.form['answers[]'][i]  # Collect the correct answer for each question
            }
            questions.append(question)

        # Save quiz in MongoDB
        quiz_data = {
            'title': quiz_title,
            'quiz_id': quiz_id,
            'questions': questions
        }

        # Assuming 'quiz_collection' is your MongoDB collection
        quiz_collection.insert_one(quiz_data)
        return redirect(url_for('admin_dashboard'))
    
    return render_template('create_regular_quiz.html')


@app.route('/create_weekend_quiz', methods=['GET', 'POST'])
def create_weekend_quiz():
    if 'user' not in session or session['user'] != ADMIN_EMAIL:
        return redirect(url_for('signin'))

    if request.method == 'POST':
        quiz_title = request.form.get('quiz_title')
        questions = request.form.getlist('questions')
        options = request.form.getlist('options')
        answers = request.form.getlist('answers')

        quiz_data = {
            'title': quiz_title,
            'questions': []
        }

        for i in range(len(questions)):
            question_data = {
                'question': questions[i],
                'options': options[i * 4:i * 4 + 4],
                'answer': answers[i]
            }
            quiz_data['questions'].append(question_data)

        db.weekend_quizzes.insert_one(quiz_data)
        flash('Weekend Quiz Created Successfully!')
        return redirect(url_for('admin_dashboard'))

    return render_template('create_weekend_quiz.html')

@app.route('/manage_students')
def manage_students():
    if 'user' not in session or session['user'] != ADMIN_EMAIL:
        return redirect(url_for('signin'))

    # Fetch all students' data from MongoDB
    students = users_collection.find()

    return render_template('manage_students.html', students=students)

@app.route('/student_dashboard')
def student_dashboard():
    if 'user' not in session or session['user'] == ADMIN_EMAIL:
        return redirect(url_for('signin'))
    
    return render_template('student_dashboard.html')


@app.route('/submit', methods=['GET', 'POST'])
def submit():
    if request.method == 'POST':
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        email = session['user']
        mobile_number = request.form.get('mobile_number')
        dob = request.form.get('dob')
        age = request.form.get('age')
        father_name = request.form.get('father_name')
        father_number = request.form.get('father_number')
        cgpa = request.form.get('cgpa')
        school_name = request.form.get('school_name')
        passout_year = request.form.get('passout_year')
        current_class = request.form.get('class')
        board_study = request.form.get('board_study')
        course = request.form.get('course')

        users_collection.update_one(
            {"email": email},
            {"$set": {
                "first_name": first_name,
                "last_name": last_name,
                "mobile_number": mobile_number,
                "dob": dob,
                "age": age,
                "father_name": father_name,
                "father_number": father_number,
                "cgpa": cgpa,
                "school_name": school_name,
                "passout_year": passout_year,
                "current_class": current_class,
                "board_study": board_study,
                "course": course,
                "form_submitted": True
            }}
        )
        return redirect(url_for('student_test', student_name=first_name))
    return render_template('studentform.html')


@app.route('/submit-quiz', methods=['POST'])
def submit_quiz():
    try:
        # Get form data
        student_name = request.form.get("student_name")
        quizID = request.form.get("quizID")
        
        # Collect answers from the request form
        user_answers = {}
        for key in request.form.keys():
            if key not in ["student_name", "quizID"]:
                user_answers[key] = request.form[key]
        
        # Calculate score based on correct answers (example correct answers dictionary)
        correct_answers = {"q1": "b"}  # Update this with actual correct answers
        score = sum(1 for q, ans in user_answers.items() if correct_answers.get(q) == ans)
        total_questions = len(correct_answers)
        
        # Prepare the result document
        quiz_result = {
            "student_name": student_name,
            "quizID": quizID,
            "user_answers": user_answers,
            "score": score,
            "total_questions": total_questions
        }

        # Insert the result document into MongoDB
        quiz_results_collection.insert_one(quiz_result)

        # Respond with success
        return jsonify({"success": True, "message": "Quiz results saved successfully."})

    except Exception as e:
        print(f"Error: {e}")  # Print error details for debugging
        return jsonify({"success": False, "message": "An error occurred while saving quiz results."})


@app.route('/results.html')
def results():
    # Fetch all results
    results = result_collection.find()
    return render_template('results.html', results=results)


@app.route('/first_year')
def first_year():
    return render_template('first_year.html')

@app.route('/FirstYear/chemistry/chemistry')  # Define the route for chemistry
def chemistry():
    return render_template('FirstYear/chemistry/chemistry.html') 

# Define routes for each chapter
@app.route('/FirstYear/chemistry/chapter1')
def chapter1():
    return render_template('FirstYear/chemistry/chapter1.html')  # Add the correct path for chapter 1

@app.route('/FirstYear/chemistry/chapter2')
def chapter2():
    return render_template('FirstYear/chemistry/chapter2.html')  # Add the correct path for chapter 2

@app.route('/FirstYear/chemistry/chapter3')
def chapter3():
    return render_template('FirstYear/chemistry/chapter3.html')  # Add the correct path for chapter 3

@app.route('/FirstYear/chemistry/chapter4')
def chapter4():
    return render_template('FirstYear/chemistry/chapter4.html')  # Add the correct path for chapter 4

@app.route('/FirstYear/chemistry/chapter5')
def chapter5():
    return render_template('FirstYear/chemistry/chapter5.html')  # Add the correct path for chapter 5

@app.route('/FirstYear/chemistry/chapter6')
def chapter6():
    return render_template('FirstYear/chemistry/chapter6.html')  # Add the correct path for chapter 6

@app.route('/FirstYear/chemistry/chapter7')
def chapter7():
    return render_template('FirstYear/chemistry/chapter7.html')  # Add the correct path for chapter 7

@app.route('/FirstYear/chemistry/chapter8')
def chapter8():
    return render_template('FirstYear/chemistry/chapter8.html')  # Add the correct path for chapter 8

@app.route('/FirstYear/chemistry/chapter9')
def chapter9():
    return render_template('FirstYear/chemistry/chapter9.html')  # Add the correct path for chapter 9

@app.route('/FirstYear/chemistry/chapter10')
def chapter10():
    return render_template('FirstYear/chemistry/chapter10.html')  # Add the correct path for chapter 10

@app.route('/FirstYear/chemistry/chapter11')
def chapter11():
    return render_template('FirstYear/chemistry/chapter11.html')  # Add the correct path for chapter 11

@app.route('/FirstYear/chemistry/chapter12')
def chapter12():
    return render_template('FirstYear/chemistry/chapter12.html')  # Add the correct path for chapter 12

@app.route('/FirstYear/chemistry/chapter13')
def chapter13():
    return render_template('FirstYear/chemistry/chapter13.html')  # Add the correct path for chapter 13

@app.route('/FirstYear/chemistry/chapter14')
def chapter14():
    return render_template('FirstYear/chemistry/chapter14.html')  # Add the correct path for chapter 14

@app.route('/FirstYear/chemistry/chapter15')
def chapter15():
    return render_template('FirstYear/chemistry/chapter15.html')  # Add the correct path for chapter 15

@app.route('/FirstYear/chemistry/chapter16')
def chapter16():
    return render_template('FirstYear/chemistry/chapter16.html')  # Add the correct path for chapter 16



@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('signin'))

def send_login_email(email, password):
    msg = Message('Login Information', recipients=[email])
    msg.body = f'You have successfully logged in to StudyTech with the following details:\nEmail: {email}\nPassword: {password}\nNow you can start learning and score best in your exams! All THE BEST!!!'
    mail.send(msg)
# Get a list of databases
dblist = client.list_database_names()

# Check if "mydatabase" exists
#if "StudyTechDB" in dblist:
 #   print("yes, 'mydatabase' exists.")
#else:
  #  print("no, 'mydatabase' does not exist.")

@app.route('/student_test')
def student_test():
    return render_template('student_test.html')

@app.route('/student_test1')
def student_test1():
    return render_template('student_test1.html')

if __name__ == '__main__':
    app.run(debug=True)