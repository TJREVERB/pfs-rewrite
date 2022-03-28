import time

lastlen = 0
while 1:
	f = open("/home/pi/pfs-rewrite/pfs-output.txt", "r")
	ls = f.readlines()
	if len(ls) > lastlen:
		print("".join(ls[lastlen:]))
	lastlen = len(ls)
	f.close()
	time.sleep(.5)
