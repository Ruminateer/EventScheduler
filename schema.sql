CREATE TABLE creds(
    useremail TEXT PRIMARY KEY,
    token TEXT NOT NULL,
    refresh_token TEXT NOT NULL
);