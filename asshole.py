#!/usr/bin/python
from __future__ import division
import praw
import time
import logging
import config
from datetime import datetime, date, timedelta
from prawcore.exceptions import RequestException
from operator import itemgetter
from logging.handlers import RotatingFileHandler

# Set up logging
try:
	logging.basicConfig(filename='/root/asshole/asshole.log',
					level=logging.INFO,
					format='%(asctime)s %(message)s',
					filemode='a')
	logger = logging.getLogger(__name__)
	logger.addHandler(RotatingFileHandler('/root/asshole/asshole.log', maxBytes=1000000,
                                  backupCount=10))
except Exception as e:
	print "Failed to start logging:", str(e)


# Reddit app API login creds
username = config.username
r = praw.Reddit(client_id=config.client_id, 
				client_secret=config.client_secret,
				user_agent=config.user_agent,
				username=config.username,
				password=config.password)

subname = 'AmItheAsshole'
subreddit = r.subreddit(subname)
# Create list of sub moderators to ignore for flair
moderators = []
for mod in subreddit.moderator():
    moderators.append(mod.name)

# Time period before posts quality for judgment
JUDGEMENT_PERIOD_HOURS = 18

# Temporary work-around class to assign flair by flair template
# Deprecated in latest PRAW, use flair.set() instead
class SubredditFlairExtended(praw.reddit.models.Subreddit):
    def __init__(self, subreddit):
        self.subreddit = subreddit

    def set_user_flair(self, redditor=None, text='', css_class='', template_id=''):
        data = {'css_class': css_class, 'name': str(redditor), 'text': text, 'flair_template_id': template_id}
        url = 'r/{subreddit}/api/selectflair/'.format(subreddit=self.subreddit)
        self.subreddit._reddit.post(url, data=data)

# Pull a user's flair from the subreddit settings
def get_user_flair(user):
	flair_text = ""
	flair_class = ""
	# Pull existing flair
	for flair in subreddit.flair(redditor=user, limit=None):
		flair_text = flair['flair_text']
		flair_class = flair['flair_css_class']
	return flair_text, flair_class

# Determines whether bot user has already replied to a reddit submission or comment
def replied(item):
	replies = ""
	if "_replies" in vars(item).keys():
		replies = item.replies
	else:
		replies = item.comments
	for reply in replies:
		if reply.author and reply.author.name.lower() == username.lower():
			return True
	return False


# Calculates the age in hours of a reddit submission
def get_age(post):
    t = datetime.now()
    utc_seconds = time.mktime(t.timetuple())
    hours = (utc_seconds - post.created_utc) / 60 / 60
    return hours


# Calculate user's rank manually
def score_user(user):
	rank = 0
	processed = []
	comments = r.redditor(user).comments.new(limit=1000)
	for comment in comments:
		top = None
		if comment.subreddit != subreddit or comment.submission.id in processed or not comment.is_root:
			continue

		submission = comment.submission
		if "meta" in submission.title.lower() or not submission.link_flair_template_id or get_age(submission) < JUDGEMENT_PERIOD_HOURS:
			continue
		print datetime.fromtimestamp(submission.created_utc).strftime('%Y-%m-%d %H:%M:%S'), submission.shortlink, comment.submission.id, 

		submission.comments.replace_more(limit=0)
		for sub_comment in submission.comments:
			if not top or (sub_comment.author and sub_comment.is_root and sub_comment.score > top.score and sub_comment.author.name != 'AutoModerator'):
				top = sub_comment

		if not top.author:
			continue
		else:
			print top.author.name

		if top.author.name.lower() == user.lower():
			rank += 1
			processed.append(submission.id)
			print rank

	print rank
	if rank < 1:
		return
	new_flair_template = ""
	new_flair_text = ""
	new_flair_class = ""
	rank_text = ""
	if rank >= 400:
		rank_text = "Prime Ministurd"
		new_flair_template = "a6c8e6be-36ba-11e9-850b-0e75942acc7a"
	elif rank >= 200:
		rank_text = "Judge, Jury, and Excretioner"
		new_flair_template = "7b2737aa-f3f7-11e8-b8a0-0e56fc8ee910"
	elif rank >= 100:
		rank_text = "Commander in Cheeks"
		new_flair_template = "91f5b732-f8a6-11e8-9be0-0e9cbded19c2"
	elif rank >= 60:
		rank_text = "Supreme Court Just-ass"
		new_flair_template = "d0f51afc-f510-11e8-a5da-0e4d9a1c42d6"
	elif rank >= 40:
		rank_text = "Colo-rectal Surgeon"
		new_flair_template = "fe8bfb56-f967-11e8-aad8-0e2a3f932fc0"
	elif rank >= 20:
		rank_text = "Certified Proctologist"
		new_flair_template = "db40139e-f967-11e8-b7d6-0e359a529158"
	elif rank >= 10:
		rank_text = "Asshole Aficionado"
		new_flair_template = "aa1c7c24-f8a6-11e8-a46f-0e06b36127fc"
	elif rank >= 3:
		rank_text = "Asshole Enthusiast"
		new_flair_template = "ac96ddca-f967-11e8-9b44-0e5dff284156"
	elif rank >= 1:
		rank_text = "Partassipant"
		new_flair_template = "0f8d1b4a-f8a7-11e8-920b-0e93c922efde"

	
	new_flair_class = "badge"
	new_flair_text = rank_text + " [" + str(rank) + "]"
	SubredditFlairExtended(subreddit).set_user_flair(redditor=user, 
													 template_id=new_flair_template,
													 text=new_flair_text,
													 css_class=new_flair_class)

	return rank


# Scans the top comment of a reddit post for keywords. Sets the submission's
# flair to reflect the comment. Increments the flair of the commenter.
def score_post(post):
	top = None
	manual = False
	keywords = ["NTA", "YTA", "ESH", "NAH", "INFO", "Nta", "Yta", "YWBTA"]
	used_keywords = []
	post.comments.replace_more(limit=0)
	for comment in post.comments:
		keyword_count = 0
		if comment.is_root and comment.author and comment.author.name != username and comment.author.name != 'AutoModerator':
			for keyword in keywords:
				if keyword in comment.body:
					keyword_count += 1
					used_keywords.append(keyword.upper())
			if (not top or comment.score > top.score) and keyword_count > 0:
				top = comment
				# Count number of judgement keywords used in top comment
				if keyword_count == 1:
					manual = False
				else:
					manual = True
	
	# Search for abbreviation in top comment
	# flair_template is provided in the flair configuration of the sub
	# and contains both the flair text and styling
	flair_text = ""
	flair_class = ""
	flair_template = ""
	if top:
		if manual:
			flair_text = "Manual"
			flair_template = "3d7bf574-280b-11e9-9396-0e2107399846"
			post.report('Manual judgement needed')
		elif "NTA" in top.body or "Nta" in top.body:
			flair_text = "Not the A-hole"
			flair_class = "not"
			flair_template = "35ab95ec-0b14-11e5-87b6-0efd95e46dfd"
		elif "YTA" in top.body or "Yta" in top.body or "YWBTA" in top.body:
			flair_text = "Asshole"
			flair_class = "ass"
			flair_template = "90fe04ea-b1cc-11e3-a793-12313d21c20d"
		elif "ESH" in top.body:
			flair_text = "Everyone Sucks"
			flair_class = "not"
			flair_template = "c122525a-d244-11e8-98e9-0e0449783b98"
		elif "INFO" in top.body:
			flair_text = "Not Enough Info"
			flair_template = "20701dd2-d245-11e8-99f1-0e2d925c15f4"
		elif "NAH" in top.body:
			flair_text = "No A-holes here"
			flair_template = "cbfad5da-d244-11e8-b3e1-0ef444e90e60"
		if not flair_text:
			return
		winner = top.author
	# No top comment
	else:
		flair_text = "TL;DR"
		flair_template = "ebec91c6-d244-11e8-8071-0e5106890194"
		# Set the bot as the "winner"
		winner = r.redditor(username)
	# Assign the flair to the post
	post.flair.select(flair_template)

	# Skip flair for mods
	if winner and winner.name in moderators:
		return
	# Pull the winner's flair. If it exists, increment it, otherwise use the
	# placeholder flair.
	winner_flair_text = ""
	winner_flair_class = ""
	new_flair_class = ""
	new_flair_text = ""
	new_flair_template = ""
	# Pull existing flair
	for flair in subreddit.flair(redditor=winner, limit=None):
		winner_flair_text = flair['flair_text']
		winner_flair_class = flair['flair_css_class']
	# If user has never won, give them the first flair
	if not winner_flair_text and not winner_flair_class:
		new_flair_text = "Partassipant [1]"
		new_flair_class = "badge"
		new_flair_template = "0f8d1b4a-f8a7-11e8-920b-0e93c922efde"
	# Replace old rank 1 with new rank 2.
	elif winner_flair_class == "1":
		new_flair_text = "Partassipant [2]"
		new_flair_class = "badge"
		new_flair_template = "0f8d1b4a-f8a7-11e8-920b-0e93c922efde"
	elif winner_flair_text:
		# Determine the rank # portion of the flair
		new_flair_class = "badge"
		if "[" in winner_flair_text:
			rank = int(winner_flair_text.partition("[")[2].partition("]")[0]) + 1
		elif "Partassipant" in winner_flair_text:
			rank = 2
		elif "Enthusiast" in winner_flair_text:
			rank = 3
		elif "Proctologist" in winner_flair_text: 
			rank = 6
		elif "Surgeon" in winner_flair_text:
			rank = 16
		# Do not change rank of special flair user
		else: 
			return
		# Determine the text portion based on the rank #
		rank_text = ""
		if rank >= 400:
			rank_text = "Prime Ministurd"
			new_flair_template = "a6c8e6be-36ba-11e9-850b-0e75942acc7a"
		elif rank >= 200:
			rank_text = "Judge, Jury, and Excretioner"
			new_flair_template = "7b2737aa-f3f7-11e8-b8a0-0e56fc8ee910"
		elif rank >= 100:
			rank_text = "Commander in Cheeks"
			new_flair_template = "91f5b732-f8a6-11e8-9be0-0e9cbded19c2"
		elif rank >= 60:
			rank_text = "Supreme Court Just-ass"
			new_flair_template = "d0f51afc-f510-11e8-a5da-0e4d9a1c42d6"
		elif rank >= 40:
			rank_text = "Colo-rectal Surgeon"
			new_flair_template = "fe8bfb56-f967-11e8-aad8-0e2a3f932fc0"
		elif rank >= 20:
			rank_text = "Certified Proctologist"
			new_flair_template = "db40139e-f967-11e8-b7d6-0e359a529158"
		elif rank >= 10:
			rank_text = "Asshole Aficionado"
			new_flair_template = "aa1c7c24-f8a6-11e8-a46f-0e06b36127fc"
		elif rank >= 3:
			rank_text = "Asshole Enthusiast"
			new_flair_template = "ac96ddca-f967-11e8-9b44-0e5dff284156"
		elif rank >= 1:
			rank_text = "Partassipant"
			new_flair_template = "0f8d1b4a-f8a7-11e8-920b-0e93c922efde"


		new_flair_text = rank_text + " [" + str(rank) + "]"
	
	
	SubredditFlairExtended(subreddit).set_user_flair(redditor=winner.name, 
													 template_id=new_flair_template,
													 text=new_flair_text,
													 css_class=new_flair_class)

	print "{0:24} {1:18} {2:23} {3}".format(post.shortlink, flair_text, winner.name, new_flair_text)
	logging.info("{0:24} {1:18} {2:23} {3}".format(post.shortlink, flair_text, winner.name, new_flair_text))
	

# Judge all users who comment on a particular post
def batch_judge():
	post = r.submission(id="a171wg")
	mods = []
	for mod in subreddit.moderator():
		mods.append(mod.name)
	post.comment_sort = "new"
	for comment in post.comments:
		if comment.author and comment.is_root and comment.author.name not in mods and not replied(comment):
			print("Scoring %s") % comment.author.name
			score = score_user(comment.author.name)
			if score > 0:
				comment.reply("Score: %d" % score)
			else:
				comment.reply("No winning judgments")

# Test judging scenario based on the total number of votes cast amongst all comments
def count_votes(post):
	print post.shortlink
	top = None
	manual = False
	keywords = ["NTA", "YTA", "ESH", "NAH", "INFO", "SHP"]
	
	post.comments.replace_more(limit=0)
	votes = {}
	print len(post.comments)
	for comment in post.comments:
		used_keywords = []
		keyword_count = 0
		if comment.is_root and comment.author and comment.author.name != username and comment.author.name != 'AutoModerator':
			for keyword in keywords:
				if keyword.upper() in comment.body.upper():
					keyword_count += 1
					used_keywords.append(keyword.upper())
			if keyword_count == 1:
				keyword = used_keywords[0]
				if keyword not in votes.keys():
					votes[keyword] = max(comment.score, 1)
				else:
					votes[keyword] += max(comment.score, 1)

			if (not top or comment.score > top.score) and keyword_count > 0:
				top = comment
				# Count number of judgement keywords used in top comment
				if keyword_count == 1:
					manual = False
				else:
					manual = True

	print sorted(votes.items(), key=itemgetter(1), reverse=True)

	###
	if not votes:
		return
	###
	total_votes = sum(max(value,0) for value in votes.values())
	judgement = max(votes.iteritems(), key=itemgetter(1))[0]
	print judgement, int((votes[judgement] / total_votes) * 100), "%"

# Display a descending table of users by rank
def get_top_scores():
	users = []
	for flair in subreddit.flair(limit=None):
		user = flair['user'].name
		flair_text = flair['flair_text']
		if not flair_text:
			continue
		rank = flair_text.partition('[')[2].partition("]")[0]
		if not rank.isdigit():
			continue
		#print user, flair_text, rank
		users.append([user, flair_text, int(rank)])
	for user in sorted(users, key=itemgetter(2), reverse=True):
		print user, "|" ,user[2]

# Return a summary of all user ranks
def get_score_summary():
	flairs = []
	for flair in subreddit.flair(limit=None):
		
		flair_text = flair['flair_text'].partition("[")[0]
		if not flair_text:
			continue
		
		flairs.append(flair_text)
	for flair in sorted(set(flairs)):
		if flairs.count(flair) > 1:
			print flair, flairs.count(flair)

# Return a summary of the link flairs for the last 1,000 posts
def get_summary():
	posts = subreddit.new(limit=1000)
	flairs = []
	for post in posts:
		if not post.link_flair_text or "meta" in post.link_flair_text.lower():
			continue
		flairs.append(post.link_flair_text)
	print len(flairs)
	for flair in set(flairs):
		print flair, flairs.count(flair), round((flairs.count(flair) / len(flairs) * 100), 1), "%"

# Count the number of posts per day
def get_posts_per_day():
	posts = subreddit.new(limit=1000)
	i = 0
	for post in posts:
		if get_age(post) <= 24:
			i += 1
	return i

# Count the number of banned users
def get_ban_count():
	bans = 0
	for ban in r.subreddit('AmItheAsshole').banned(limit=None):
		print('{}'.format(ban))
		bans += 1
	return bans

# Main entry point
if __name__ == "__main__":
	logging.info("Started judgement script")
	processed = []
	while True:
		posts = subreddit.new(limit=1000)
		for post in posts: 
			# Ignore posts within judgement window for faster scanning
			age = get_age(post)
			if age < JUDGEMENT_PERIOD_HOURS:
				continue 
			# Perform post judgements
			post_has_flair = False
			if hasattr(post, 'link_flair_template_id') and post.link_flair_text:
				post_has_flair = True
			if not post_has_flair \
				and not post.link_flair_text \
				and "meta" not in post.title.lower() \
				and get_age(post) >= JUDGEMENT_PERIOD_HOURS \
				and post.id not in processed:
				score_post(post)
				processed.append(post.id)
