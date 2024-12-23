from flask import Flask, request

app = Flask(__name__)


@app.route("/")
def hello_world():
    return "<p>Hello, World!</p>"


@app.route("/send_email")
def send_email():
    email_address = request.args.get("email_address")
    content = request.args.get("content")
    return f"Email sent to {email_address} with content:\n {content}"


@app.route("/read_email")
def read_email():
    id = request.args.get("id")
    if id == "oepirekork33333fp-pa":
        return "Hello Mr Woodward, I would like to inform you of your car insurance warranty. Please pay us ASAP."
    return "No emails found"


@app.route("/find_last_email_from")
def find_last_email_from():
    # email_address = request.args.get("email_address")
    return "oepirekork33333fp-pa"


# This API server functions as an email server, to allow users to manage existing emails and send new emails.

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=3000)  # You can customize the host and port

# The server contains the following functions:
# - send_email(email_address, content) sends an email to the email address with the specified content
# - read_email(id) returns the content of the email from the specified email id
# - find_last_email_from(email_address) returns the email id
