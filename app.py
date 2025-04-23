import os
import pandas as pd
from flask import Flask, render_template, redirect, request, session, url_for, make_response
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin

app = Flask(__name__, template_folder="templates")
app.secret_key = "your_secret_key"  # Required for session management

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"  # Redirect to the login page if not authenticated

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, id):
        self.id = id

# Load user callback
@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

# Define the structure of the polls
structure = {
    "id": [],
    "poll": [],
    **{f"option{i}": [] for i in range(1, 43)},  # Add options 1 to 42
    **{f"vote{i}": [] for i in range(1, 43)},    # Add votes 1 to 42
}

# Initialize the polls.csv file
def initialize_polls_file():
    if not os.path.exists("polls.csv"):
        structure = {
            "id": [],
            "poll": [],
            **{f"option{i}": [] for i in range(1, 43)},
            **{f"vote{i}": [] for i in range(1, 43)},
        }
        pd.DataFrame(structure).to_csv("polls.csv", index=False)

initialize_polls_file()

# Initialize the users.csv file
def initialize_users_file():
    if not os.path.exists("users.csv"):
        users_structure = {"username": [], "password": []}
        pd.DataFrame(users_structure).to_csv("users.csv", index=False)

initialize_users_file()

# Load the polls data
try:
    polls_df = pd.read_csv("polls.csv").drop_duplicates(subset="id").set_index("id")
except (pd.errors.EmptyDataError, KeyError):
    polls_df = pd.DataFrame(columns=["id", "poll", "option1", "option2", "option3", "vote1", "vote2", "vote3"]).set_index("id")

@app.before_request
def require_login():
    allowed_routes = ["login", "signup", "static"]  # Routes that don't require login
    if "username" not in session and request.endpoint not in allowed_routes:
        print(f"Redirecting to login. Current session: {session}")  # Debugging
        return redirect("/login")

@app.route("/")
def index():
    print(f"Logged in user: {session.get('username')}")
    return render_template("index.html", polls=polls_df, username=session.get("username"))

@app.route("/polls/<id>")
def show_poll(id):
    global polls_df
    try:
        id = int(id)  # Ensure the ID is an integer
        print(f"Accessing poll ID: {id}")  # Debugging: Print the poll ID
        print(f"Polls DataFrame:\n{polls_df}")  # Debugging: Print the DataFrame

        if id not in polls_df.index:
            print("Poll ID not found in DataFrame.")  # Debugging
            return "Poll not found", 404

        poll = polls_df.loc[id]
        options = [(i, poll[f"option{i}"]) for i in range(1, 43) if pd.notna(poll[f"option{i}"])]
        print(f"Poll Data: {poll}")  # Debugging: Print the poll data
        print(f"Options: {options}")  # Debugging: Print the options
        return render_template("show_poll.html", poll=poll, options=options)
    except (ValueError, KeyError) as e:
        print(f"Error: {e}")  # Debugging: Print the error
        return "Invalid poll ID", 400

@app.route("/polls", methods=["GET", "POST"])
def create_poll():
    global polls_df
    if "username" not in session:
        return redirect("/login")
    if request.method == "POST":
        # Extract data from the form
        new_poll = pd.DataFrame([{
            "id": polls_df.index.max() + 1 if not polls_df.empty else 1,  # Generate a new ID
            "poll": request.form["poll"],
            **{f"option{i}": request.form.get(f"option{i}", "") for i in range(1, 43)},  # Get all options
            **{f"vote{i}": 0 for i in range(1, 43)},  # Initialize votes to 0
        }])
        # Append the new poll to the DataFrame
        polls_df = pd.concat([polls_df, new_poll.set_index("id")])
        # Save the updated DataFrame to the CSV file
        polls_df.to_csv("polls.csv")
        return redirect("/")
    return render_template("new_poll.html")

@app.route("/vote/<id>", methods=["POST"])
def vote(id):
    global polls_df
    if "username" not in session:
        return redirect("/login")
    try:
        id = int(id)  # Ensure the ID is an integer
        print(f"Accessing poll ID for voting: {id}")  # Debugging
        print(f"Polls DataFrame:\n{polls_df}")  # Debugging

        if id not in polls_df.index:
            print("Poll ID not found in DataFrame.")  # Debugging
            return "Poll not found", 404

        option = request.form["option"]  # Get the selected option from the dropdown
        print(f"Option received: {option}")  # Debugging

        if option not in [f"option{i}" for i in range(1, 43)]:
            print("Invalid option selected.")  # Debugging
            return "Invalid option", 400

        # Check if the user has already voted for this poll
        poll_cookie = request.cookies.get(f"voted_poll_{id}")
        if poll_cookie:
            print("User has already voted for this poll.")  # Debugging
            return "You have already voted for this poll", 403

        vote_column = f"vote{option[-1:]}"  # Extract the vote column dynamically
        if vote_column not in polls_df.columns:
            print("Vote column not found in DataFrame.")  # Debugging
            return "Invalid option", 400

        # Increment the vote count
        polls_df[vote_column] = polls_df[vote_column].fillna(0).astype(int)
        polls_df.loc[id, vote_column] += 1
        # Save the updated DataFrame to the CSV file
        polls_df.to_csv("polls.csv")

        # Set a cookie to indicate the user has voted
        response = make_response(redirect("/"))
        response.set_cookie(f"voted_poll_{id}", "true", max_age=60 * 60 * 24)  # Cookie expires in 1 day
        return response
    except (ValueError, KeyError) as e:
        print(f"Error: {e}")  # Debugging: Print the error
        return "Invalid request", 400

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        # Load users data
        users_df = pd.read_csv("users.csv")

        # Check if the username already exists
        if username in users_df["username"].values:
            return "Username already exists", 400

        # Add the new user
        new_user = pd.DataFrame([{"username": username, "password": password}])
        users_df = pd.concat([users_df, new_user], ignore_index=True)
        users_df.to_csv("users.csv", index=False)

        return redirect("/login")
    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        # Load users data
        users_df = pd.read_csv("users.csv")

        # Check if the username and password match
        if username in users_df["username"].values:
            user = users_df[users_df["username"] == username]
            if user["password"].values[0] == password:
                session["username"] = username  # Set the session
                print(f"Logged in user: {session['username']}")  # Debugging
                return redirect("/")
        return "Invalid username or password", 400
    return render_template("login.html")

@app.route("/logout", methods=["POST"])
def logout():
    session.pop("username", None)
    return redirect("/login")

if __name__ == "__main__":
    app.run(host="localhost", debug=True)