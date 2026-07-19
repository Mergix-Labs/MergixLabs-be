def forgot_password_template(name,link):
    return f'''
    <html>
    <head>
    <style>
    .container{{
        width: 100%;
        padding: 10px;
        background-color: #f1f1f1;
    }}
    .content{{
        width: 50%;
        margin: 0 auto;
        padding: 10px;
        background-color: white;
    }}
    </style>
    </head>
    <body>
    <div class="container">
        <div class="content">
            <h1>Forgot Password?</h1>
            <p>Hi {name},</p>
            <p>We received a request to reset your password. Click on the link below to reset your password.</p>
            <a href="{link}">Reset Password</a>
            <p>If you did not request a password reset, please ignore this email.</p>
        </div>
    </div>
    </body>
    </html>
    '''