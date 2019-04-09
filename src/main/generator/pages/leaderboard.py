from code.util.db import Submission, User, Contest, Problem
from code.generator.lib.htmllib import *
from code.generator.lib.page import *
import logging
from code.util import register
import time
from datetime import datetime

def leaderboard(params, user):
    contest = Contest.getCurrent() or Contest.getPast()
    if not contest:
        return Page(
            h1("&nbsp;"),
            h1("No Contest Available", cls="center")
        )
    elif contest.scoreboardOff <= time.time() * 1000 and not user.isAdmin():
        return Page(
            h1("&nbsp;"),
            h1("Scoreboard is off.", cls="center")
        )

    start = contest.start
    end = contest.end

    
    subs = {}
    for sub in Submission.all():
        if start <= sub.timestamp <= end and not sub.user.isAdmin():
            subs[sub.user.id] = subs.get(sub.user.id) or []
            subs[sub.user.id].append(sub)            
    
    problemSummary = {}
    for prob in contest.problems:
        problemSummary[prob.id] = [0, 0]

    scores = []
    for user in subs:
        usersubs = subs[user]
        scor = score(usersubs, start, problemSummary)
        scores.append((
            User.get(user).username,
            scor[0],
            scor[1],
            scor[2],
            len(usersubs)
        ))
    scores = sorted(scores, key=lambda score: score[1] * 1000000000 + score[2] * 10000000 - score[3], reverse=True)
    
    ranks = [i + 1 for i in range(len(scores))]
    for i in range(1, len(scores)):
        u1 = scores[i]
        u2 = scores[i - 1]
        if (u1[1], u1[2], u1[3]) == (u2[1], u2[2], u2[3]):
            ranks[i] = ranks[i - 1]
    
    scoresDisplay = []
    for (name, solved, samples, points, attempts), rank in zip(scores, ranks):
        scoresDisplay.append(h.tr(
            h.td(rank, cls="center"),
            h.td(name),
            h.td(attempts, cls="center"),
            h.td(solved, cls="center"),
            h.td(samples, cls="center"),
            h.td(points, cls="center")
        ))

    problemSummaryDisplay = []
    for problem in contest.problems:
        
        problemSummaryDisplay.append(h.tr(
            h.td(problem.title),
            h.td(problemSummary[problem.id][0], cls="center"),
            h.td(problemSummary[problem.id][1], cls="center")
        ))

    return Page(
        h2("Leaderboard", cls="page-title"),
        div(cls="actions", contents=[
            h.button("Correct Log Report", cls="button create-message",onclick="window.location.href='/correctboard'")
        ]),
        h.table(
            h.thead(
                h.tr(
                    h.th("Rank", cls="center"),
                    h.th("User"),
                    h.th("Attempts", cls="center"),
                    h.th("Problems Solved", cls="center"),
                    h.th("Sample Cases Solved", cls="center"),
                    h.th("Penalty Points", cls="center")
                )
            ),
            h.tbody(
                *scoresDisplay
            )
        ),
        h2("Problem Summary", cls="page-title"),
        h.table(
            h.thead(
                h.tr(
                    h.th("Problem", cls="center"),
                    h.th("Attempts", cls="center"),
                    h.th("Solved", cls="center"),
                )
            ),
            h.tbody(
                *problemSummaryDisplay
            )

        )
    )

def correctboard(params, user):
    contest = Contest.getCurrent() or Contest.getPast()
    if not contest:
        return Page(
            h1("&nbsp;"),
            h1("No Contest Available", cls="center")
        )
    elif contest.scoreboardOff <= time.time() * 1000 and not user.isAdmin():
        return Page(
            h1("&nbsp;"),
            h1("Scoreboard is off.", cls="center")
        )

    start = contest.start
    end = contest.end

    correct = []
    for sub in Submission.all():
        if start <= sub.timestamp <= end and sub.result == "ok" and not sub.user.isAdmin(): # USE THIS TOO
            username = User.get(sub.user.id).username
            title    = Problem.get(sub.problem.id).title
            notinlist = True
            
            for c in correct:
                if c.get("username") == username and c.get("title") == title and c.get("timestamp") > sub.timestamp:
                    c["timestamp"] = sub.timestamp
                    notinlist = False
                    break
                elif c.get("username") == username and c.get("title") == title and c.get("timestamp") < sub.timestamp:
                    notinlist = False
                    break
            
            if notinlist: correct.append({ "timestamp":sub.timestamp,"username":username,"title":title})
                
     
    correct.sort(key=lambda item:item['timestamp'], reverse=True)
    for c in correct:
        c["timestamp"] = datetime.utcfromtimestamp(c["timestamp"] / 1000).strftime('%Y-%m-%d %H:%M:%S')

    problemCorrectDisplay = []
    for c in correct:
        problemCorrectDisplay.append(h.tr(
            h.td(c["timestamp"]),
            h.td(c["username"], cls="center"),
            h.td(c["title"], cls="center")
        ))

    return Page(
        h2("Correct Log Report", cls="page-title"),
        h.table(
            h.thead(
                h.tr(
                    h.th("Date/Time"),
                    h.th("Contestent", cls="center"),
                    h.th("Problem", cls="center"),
                )
            ),
            h.tbody(
                *problemCorrectDisplay
            )

        )
    )

def score(submissions: list, contestStart, problemSummary) -> tuple:
    """ Given a list of submissions by a particular user, calculate that user's score.
        Calculates score in ACM format. """
    
    solvedProbs = 0
    sampleProbs = 0
    penPoints = 0

    # map from problems to list of submissions
    probs = {}

    # Put the submissions into the probs list
    for sub in submissions:
        probId = sub.problem.id
        if probId not in probs:
            probs[probId] = []
        probs[probId].append(sub)
    
    # For each problem, calculate how much it adds to the score
    for prob in probs:
        # Sort the submissions by time
        subs = sorted(probs[prob], key=lambda sub: sub.timestamp)
        # Penalty points for this problem
        points = 0
        solved = False
        sampleSolved = False
        
        for sub in subs:
            for res in sub.results[:sub.problem.samples]:
                if res != "ok":
                    break
            else:
                sampleSolved = True
            if sub.result != "ok":
                # Unsuccessful submissions count for 20 penalty points
                # But only if the problem is eventually solved
                points += 20
            else:
                # The first successful submission adds a penalty point for each
                #     minute since the beginning of the contest
                # The timestamp is in millis
                points += (sub.timestamp - contestStart) // 60000
                solved = True
                break
        
        # Increment attempts
        problemSummary[sub.problem.id][0] += 1

        # A problem affects the score only if it was successfully solved
        if solved:
            solvedProbs += 1
            penPoints += points
            problemSummary[sub.problem.id][1] += 1
        elif sampleSolved:
            sampleProbs += 1
    
    # The user's score is dependent on the number of solved problems and the number of penalty points
    return solvedProbs, sampleProbs, int(penPoints)

register.web("/leaderboard", "loggedin", leaderboard)
register.web("/correctboard", "admin", correctboard)
