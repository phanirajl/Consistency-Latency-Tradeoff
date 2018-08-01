class Op:
	__slots__=['_index','_type','_start','_finish']

	def __init__(self,index,opType,start,finish):
		self._index = index
		self._type = opType
		self._start = start
		self._finish =finish

	def __str__(self):
		s = "Op.index:"+str(self._index)+" opType:"+str(self._type)+" start time:"+str(self._start)+" finish time:"+str(self._finish)
		return s
