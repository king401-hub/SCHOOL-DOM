# ngrok.yml
version: "2"
authtoken: 383sn8gZb7gX6rDjOfeZNwmChyp_54mPiGRrYHCg3cMY17Cue

tunnels:
  react:
    domain: eliana-cecal-unpitiably.ngrok-free.dev
    proto: http
    addr: 5173
    inspect: true
  
  django:
    proto: http
    addr: 8000
    inspect: true