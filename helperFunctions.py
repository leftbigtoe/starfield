import viz
import viztask
import vizshape
import math
import vizact
import csv
import time
import serial
import random
import pickle



#### set up #####

def createWorld(HMDsensor = None, startingPoint = [0,0,0], fog = True):
	"""
	sets up an optical flow environment using the build in precipation 
	particle system a sphere (to lower visibility range to avoid visual 
	artifacts) and the mainView are linked to an (invisible) avatar
	TESTED
	"""

	# set up view
	view = viz.MainView
	 
	# sphere restrict visibility range (otherwise vision artifacts)
	bubble = vizshape.addSphere(radius = 1000, 
			 slices=20, stacks=20, cullFace = False)
	bubble.color(viz.BLACK)

	# wheelbarrow (to attach view & bubble to)
	avatar = viz.add('wheelbarrow.ive')
	avatar.setPosition(startingPoint)
	avatar.visible(viz.OFF) # uncomment for debugging

	# link viewpoint and object (uncomment for debugging)
	viz.link(avatar, viz.MainView)
	# link bubble to object
	viz.link(avatar, bubble)
	# eventually, link polhemus to mainview
	if not HMDsensor == None:
		lnk  = viz.link(avatar, viz.MainView)
		lnk.preMultLinkable(HMDsensor)
	
	# add starfield as action to action pool 1
	avatar.addAction(addStarfield(nStars = 12000, starSize = 0.17, colDimXYZ = [6, 30, 6],
							      nColsXYZ = [21, 1, 21], fog = fog), 1)
	
	return avatar



##### task control ######

def resetTask(avatar, resetStarfield = True, tm = None):
	"""
	resets the position of the avatar after the trial
	TESTED
	"""
	# create black quad for fading
	blackScreen = viz.addTexQuad(parent=viz.SCREEN,scale=[100.0]*3,color=viz.BLACK)
	blackScreen.alpha(0.0)
	
	# fade out
	fadeOut = vizact.fadeTo(1.0,time=2.0)
	blackScreen.addAction(fadeOut)
	yield viztask.waitActionEnd(blackScreen, fadeOut)

	# remove old starfield
	if resetStarfield:
		avatar.clearActions(pool = 1)
	
	if not(tm == None):
		tm.__del__()
		
	# reset position & heading
	yield avatar.setPosition([0,0,0])
	yield avatar.setAxisAngle([0,1,0,0])
	
	# create new starfield
	if resetStarfield:
		avatar.addAction(addStarfield(), pool = 1)
	
	# fade in
	fadeIn = vizact.fadeTo(0.0,time=2.0)
	blackScreen.addAction(fadeIn)
	yield viztask.waitActionEnd(blackScreen, fadeIn)
	blackScreen.remove()



#### homing vector calcultion and saving stuff ####

def transformReferenceFrame(heading360, alpha360):
	""" 
	given the heading and a certain angle alpha it expresses alpha one frame
	(egocentric or allocentric) it expresses alpha in the other frame
	USE 360 DEGREE SYSTEM ANGLES ONLY!!!
	"""	
	# substract smaller angle from bigger angle
	if heading360 > alpha360:
		transformed = heading360 - alpha360
	else:
		transformed = alpha360 - heading360
	
	# magical bugfix, not exactly know why
	# fixes sign error for left turns
	transformed  *= -1 if heading360  > 180 else 1	
	
	# return converted to 180 degree sys
	transformed = transform360To180(transformed)
	
	return transformed
	
	
def transformAxisAngleTo360(axisAngle, axis = 1):
	""" expresses orientation info from getAxisAngle in a 360 degrees system (2D!!!) """
	angle360 = (360 + axisAngle[axis] * axisAngle[3]) % 360
	return angle360
	
	
def transform360To180(angle):
	""" expresses angles in 360 degree system as +/- 180 degree angles (clockwise beeing positiv) """
	angle180 = angle - 360 if angle > 180 else angle
	return angle180
	
	
def transformAxisAngleTo180(axisAngle, axis = 1):
	""" transforms axisAngle data to a proper +/- 180 representation """
	angle360 = transformAxisAngleTo360(axisAngle, axis)
	angle180 = transform360To180(angle360)
	return angle180


def saveHomingVectors(avatar, output):
	""" 
	calculates the correct homing vectors for egocentric and allocentric reference frames
	and saves them to the output dict
	"""
	# create helper object at the same position as the avatar
	ignisFatuus = vizshape.addCube(size=1.0)
	ignisFatuus.visible(viz.OFF)
	yield ignisFatuus.setPosition(avatar.getPosition())
	# let it look to the starting point
	yield ignisFatuus.lookAt([0,0,0])
	# get heading (avatarAxis) and allocentric homing in weird vizard coordinates
	ignisAxis 	= ignisFatuus.getAxisAngle(viz.ABS_GLOBAL)
	avatarAxis  = avatar.getAxisAngle(viz.ABS_GLOBAL)
	
	# convert to 360 system
	heading360 = transformAxisAngleTo360(avatarAxis)
	allo360    = transformAxisAngleTo360(ignisAxis)
	
	# get homing vectors in proper coordinates & save to output
	output['alloHomingVector'] = transformAxisAngleTo180(ignisAxis, axis = 1)
	output['egoHomingVector']  = transformReferenceFrame(heading360, allo360)





##########################################################################
##                              classes                                 ##
##########################################################################


class Starfield(viz.ActionClass):
	"""
	action class providing a starfield that can be used as optical flow stimulus
	"""
	
	def begin(self,object):
		"""
		constructor: places the stars randomly columns around a column
		center (black cube). columns are stored in a list
		
		"""
		self.data 	   = self._actiondata_.data
		self.nStars    = self.data[0]
		self.starSize  = self.data[1]
		self.colDimXYZ = self.data[2]
		self.nColsXYZ  = self.data[3]
		
		# internal parameters
		self.starsPerColumn = int(self.nStars / (self.nColsXYZ[0] * 
							  self.nColsXYZ[1] * self.nColsXYZ[2]))
		self.xDeltaMax = self.colDimXYZ[0] * self.nColsXYZ[0] / 2
		self.yDeltaMax = self.colDimXYZ[1] * self.nColsXYZ[1] / 2
		self.zDeltaMax = self.colDimXYZ[2] * self.nColsXYZ[2] / 2
		self.countStart = 0
		self.time = 0

		# create a master star
		protoStar = viz.addTexQuad(size = self.starSize)
		protoStar.setPosition([0,1,1])
		diff = viz.add('star.png')
		#norm = viz.add('normal1.tif') 
		protoStar.texture(diff,'',1)
		#protoStar.bumpmap(norm,'',0) does not work with the fog
		protoStar.billboard(mode=viz.BILLBOARD_VIEW)
		
		# list with all stars
		self.columns = []
		for idx_x in range(self.nColsXYZ[0]):
			for idx_y in range(self.nColsXYZ[1]):
				for idx_z in range(self.nColsXYZ[2]):
					# create center node as parent for all stars in that column
					columnCenter = vizshape.addCube(size = 0.001)
					columnCenter.color(viz.BLACK)
					columnCenter.setPosition([idx_x * self.colDimXYZ[0],
											  idx_y * self.colDimXYZ[1],
											  idx_z * self.colDimXYZ[2]])
					self.columns.append(columnCenter)
					# randomly create stars within the limits of one column
					for y in range(self.starsPerColumn):
						# positioning
						x = self.colDimXYZ[0] * (random.random() - 0.5)
						y = self.colDimXYZ[1] * (random.random() - 0.5)
						z = self.colDimXYZ[2] * (random.random() - 0.5)
						star = protoStar.clone(columnCenter)
						star.setPosition([x,y,z], mode = viz.ABS_PARENT)
						star.billboard(mode=viz.BILLBOARD_VIEW)
		
		protoStar.remove()



	def update(self,elapsed,object):
		"""
		checks every frame if a column center exceeded the volume
		if yes, it reenters the volume on the oppsite side (like in snake)
		"""

		# get position of the avatar (center of the field)
		[aX, aY, aZ] = object.getPosition(mode = viz.ABS_GLOBAL)
		# for every star: check if within limits of field, if not, reposition using respawn function
		for column in self.columns[self.countStart::4]:
			# get position of the star
			pos = column.getPosition(mode = viz.ABS_GLOBAL)
			# check every coordinate
			x = pos[0] if abs(pos[0] - aX) <= self.xDeltaMax else self.respawn(aX, pos[0], self.xDeltaMax)
			y = pos[1] if abs(pos[1] - aY) <= self.yDeltaMax else self.respawn(aY, pos[1], self.yDeltaMax)
			z = pos[2] if abs(pos[2] - aZ) <= self.zDeltaMax else self.respawn(aZ, pos[2], self.zDeltaMax)

			self.time = elapsed + self.time
			
			# eventually reposition
			column.setPosition([x,y,z], mode = viz.ABS_GLOBAL)
			
		self.countStart = (self.countStart + 1) % 4
		
		if self.time >= 200.00 and self.time <= 200.1:
			object.setPosition([0,0,0], viz.ABS_GLOBAL)
			
		
	def end(self,object):
		for column in self.columns:
			column.remove()
		print 'starfield ended'		
		
		
	def respawn(self, cAvatar, cPoint, deltaMax):
		""" if point exceeded displayed field, this calculates the reentry coordinates """
		# transform into coordinate system with avatar as (0,0)
		delta  = cPoint - cAvatar
		# how far the point exceeded the limit
		rest   = abs(delta) % deltaMax
		# check on which side
		side   = -1 if cPoint < cAvatar else 1
		# calculate new coordinates in global sys after entering on the other side
		new    = cAvatar - side * (deltaMax - rest)
		return new


def addStarfield(nStars = 10000, starSize = 0.18, colDimXYZ = [5, 30, 5], nColsXYZ = [20, 1, 20], fog = True):
	"""
	creates a starfield around the object it is assigned to as action
	object is center and the cuboid has the edge lenghts dimX, dimY and dimZ
	every frame every star is checked if it exceeds the cuboid, if yes it reenters
	the cuboid on the other side (like playing good old snkae)
	"""	
	
	if fog:
		fogEnd = max([a*b for a,b in zip(colDimXYZ,nColsXYZ)]) / 2
		fogStart = fogEnd - 2 * min(colDimXYZ)
		viz.fog(fogStart,fogEnd)				
		viz.fogcolor(viz.BLACK)
		
	bla 			= viz.ActionData()
	bla.data 		= [nStars, starSize, colDimXYZ, nColsXYZ]
	bla.actionclass	= Starfield
	return bla
