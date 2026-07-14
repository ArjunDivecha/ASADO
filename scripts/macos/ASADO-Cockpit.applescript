property launcherPath : "/Applications/ASADO Cockpit.app/Contents/Resources/asado-cockpit-server.sh"

on startCockpit()
	do shell script quoted form of launcherPath & " start"
end startCockpit

on run
	startCockpit()
end run

on reopen
	startCockpit()
end reopen

on idle
	return 60
end idle

on quit
	try
		do shell script quoted form of launcherPath & " stop"
	end try
	continue quit
end quit
