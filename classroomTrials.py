
import helperFunctions
import viz
import vizact
import viztask

class passageActionClass(viz.ActionClass):
	
	def begin(self, object):
		"""
		constructor, gets parameters from self.data object (see vizard tutorial for writing own
		action classes to understand those weird ways)
		"""
		# get data
		self.data = self._actiondata_.data
		self.turningAngle 	= self.data[0]
		self.vLinear 		= self.data[1]	
		self.tLegs 			= self.data[2]
		self.tAccLin	 	= self.data[3]
		
		# set internal parameters
		self.t 				= 0
		self.direction 		= -1 if self.turningAngle < 0 else 1
		self.accHeading 	= 0
		self.currentHeading = object.getAxisAngle(viz.ABS_GLOBAL)[3]
		self.aTurn			= 15  	# fixed turn aceleration, be cautious with higher values (nausea)
		self.vLinCurrent	= 0.0

		# calculate linear acceleration time needed
		self.aLinear = self.vLinear / self.tAccLin
		
		# time after half the turn is done and deccelerating can begin
		self.tAccCirc = (abs(self.turningAngle)/self.aTurn)**0.5		
		
		
	def update(self, elapsed, object):
		"""
		update function, executed every frame
		"""
		### updating parameters
		# Update time
		tLast = self.t
		self.t += elapsed

		
		### control turn movement
		deltaSCirc = 0
		# get turn time (=0 at beginning of turn)
		timeCirc = self.t - (self.tLegs[0] + self.tAccLin)
		## accelerating part of the turn
		if 0 < timeCirc and timeCirc <= self.tAccCirc:			
			# calculate Heading after certain time of accelerating the turn (save in buffer)
			self.accHeading = 0.5 * self.aTurn * timeCirc**2
			# if still accelerating, take value as current heading
			self.currentHeading = self.accHeading
			
		## decelerating part of the turn
		if self.tAccCirc < timeCirc and timeCirc <= 2*self.tAccCirc:
			# displacement via constant speed after acceleration - 'deceleration movement'
			self.currentHeading = ((self.aTurn * self.tAccCirc) * (timeCirc - self.tAccCirc)) - (
								  0.5 * self.aTurn * (timeCirc - self.tAccCirc)**2) + self.accHeading
		
		
		### control linear movement
		# normally constant linear movement, during acceleration phases overwritten
		deltaS = elapsed * self.vLinear
		
		## accelerate linear movement
		if self.t <= self.tAccLin:
			# calculate linear movement since last frame (overwrite linear deltaS)
			deltaS =  0.5 * self.aLinear * self.t**2 - 0.5 * self.aLinear * tLast**2

		## decelerate linear movement
		timeLin = self.t - (self.tLegs[0] + self.tLegs[1] + self.tAccLin + 2 * self.tAccCirc)
		if 0 < timeLin:
			# deceleration deltaS is linear movement - deceleration during last frame
			deltaS = (self.vLinear * elapsed) - (  0.5 * self.aLinear *  timeLin            ** 2 
											     - 0.5 * self.aLinear * (timeLin - elapsed) ** 2)
			
			
		### end movement object eventually
		if deltaS < 0:
			self.end(object)
	
		### updating position of the virtual avatar
		# update avatar according to linear displacement
		object.setPosition([0,0,deltaS], viz.ABS_LOCAL)
		
		# update avatar orientation
		object.setAxisAngle([0,1,0,self.currentHeading * self.direction],viz.ABS_GLOBAL)

		# save current heading as last heading
		self.lastHeading  = self.currentHeading
		
		
	def end(self, object):	
		# finally, the end		
		viz.ActionClass.end(self,object)
	
	
def passageAction(turningAngle, vLinear = 8, tLegs = [3,4], tAccLin = 1):
	"""
	create a passage action independent of the treadmill. Offers linearly
	accelerated linear and turn move.
	turningAngle: 	total angle of the turn (negative for left turns)
	vLinear:      	max linear speed
	tLegs:		  	purely linear (straight) movement without turn 
	tAccLin:		time used for accelerating to vLinear (adds to tLegs)
	"""
	bla = viz.ActionData()
	bla.data =[turningAngle, vLinear, tLegs, tAccLin]
	bla.actionclass = passageActionClass
	return bla	


def strippedTrialTask(avatar, turningAngle, vLinear, tLegs, idxTrial, output = {}):
	"""
	master task that invokes all other tasks as subtasks to ensure right order
	"""
	# add text for instructions
	screenText = viz.addText('trial no. '+str(idxTrial),viz.SCREEN)
	screenText.setBackdrop(viz.BACKDROP_RIGHT_BOTTOM)
	screenText.setBackdropColor(viz.GRAY)
	screenText.setPosition(0.05, 0.5)
	
	# wait for key press and execute trial
	yield viztask.waitKeyDown(' ')
	screenText.message('')
	passage = passageAction(turningAngle, vLinear, tLegs)
	avatar.addAction(passage)
	yield viztask.waitActionEnd(avatar, passage)
	
	# get homing vectors
	yield helperFunctions.saveHomingVectors(avatar, output)
	print output
	
	# post trial instructions & position reset
	yield viztask.waitTime(0.2)
	screenText.message('please select your\nanswer for trial '+str(idxTrial))
	yield viztask.waitKeyDown(' ')
	screenText.remove()
	yield helperFunctions.resetTask(avatar)


def multipleTrialTask(avatar, angles):
	"""
	function to call multiple trials (needs to be a task to ensure proper time course)
	"""
	counter = 1
	for angle in trialDict['turningAngles']:
		output = {}
		yield viztask.waitTask(strippedTrialTask(avatar, angle, trialDict['vLinear'], 
												 trialDict['tLegs'], counter))
		counter+=1
	# add text for instructions
	screenText = viz.addText('please open and fill out\nthe questionnaires now',viz.SCREEN)
	screenText.setBackdrop(viz.BACKDROP_RIGHT_BOTTOM)
	screenText.setBackdropColor(viz.GRAY)
	screenText.setPosition(0.05, 0.5)


## set up world 
avatar = helperFunctions.createWorld()
viz.go(viz.FULLSCREEN)

## set parameters here
outputDict = {}
trialDict = {'turningAngles':[-60, 90, -90, 60], 'vLinear':10, 'tLegs':[2,3]}

# starts execution of the script by scheduling the multipleTrialTask		
viztask.schedule(multipleTrialTask(avatar, trialDict))

