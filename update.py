#!/usr/bin/env python

import github

import argparse
import glob
import os
import shutil
import subprocess
import sys
import tarfile
import urllib

parser = argparse.ArgumentParser()
parser.add_argument(
	"--github-access-token",
	dest = "githubAccessToken",
	default = os.environ.get( 'GITHUB_ACCESS_TOKEN', None ),
	help = "A suitable access token to authenticate the GitHub API."
)
parser.add_argument(
	"--set-outputs",
	dest = "setOutputs",
	default = False,
	action = "store_true",
	help = "Echo the outputs needed by `.github/workflows/update.yml`."
)
args = parser.parse_args()

def __versionFromString( s ) :

	# We use a list of ints for the version, as it
	# can be compared usefully.
	try :
		return [ int( n ) for n in s.split( "." ) ]
	except :
		# We don't care about non-numeric releases
		# like betas etc.
		return [ 0, 0, 0, 0 ]

def __versionToString( v ) :

	return ".".join( str( s ) for s in v )

# Find the latest release

client = github.Github( args.githubAccessToken )
repo = client.get_repo( "GafferHQ/gaffer" )

latestRelease = None
latestReleaseVersion = __versionFromString( "0.0.0.0" )

for release in repo.get_releases() :

	if release.prerelease :
		continue

	releaseVersion = __versionFromString( release.tag_name )
	if releaseVersion > latestReleaseVersion :
		latestRelease = release
		latestReleaseVersion = releaseVersion

# # If its up to date with the latest documented version, then we're done

latestDocVersion = max( [ __versionFromString( v ) for v in glob.glob( "*.*.*.*" ) ] )
if latestReleaseVersion <= latestDocVersion :
	sys.stderr.write( "Up to date\n" )
	sys.exit( 0 )

# Otherwise we should download the release and add the docs to this repo

packageName = "gaffer-{}-linux".format( __versionToString( latestReleaseVersion ) )

assetToDownload = None
assets = latestRelease.get_assets()
for asset in assets :
	if asset.name == "{}.tar.gz".format( packageName ) :
		assetToDownload = asset

if assetToDownload is None :
	sys.stderr.write( "Asset not found for release {}\n".format( latestRelease.title ) )
	sys.exit( 1 )

# Download and unpack docs into place

sys.stderr.write( "Downloading {}\n".format( assetToDownload.browser_download_url ) )

downloadStream = urllib.request.urlopen( assetToDownload.browser_download_url )

tarFile = tarfile.open( fileobj = downloadStream, mode= "r|gz" )
tarFile.extractall( path = "/tmp" )

shutil.copytree(
	"/tmp/{}/doc/gaffer/html".format( packageName ),
	"./{}".format( __versionToString( latestReleaseVersion ) )
)
subprocess.call( [ "git", "add", "./{}".format( __versionToString( latestReleaseVersion ) ) ] )

# Update index.html to redirect to latest version

with open( "index.html.in" ) as indexIn, open( "index.html", "w" ) as indexOut :
	for line in indexIn.readlines() :
		indexOut.write( line.format( latestReleaseVersion = __versionToString( latestReleaseVersion ) ) )

subprocess.call( [ "git",  "add",  "./index.html" ] )

sys.stderr.write( "Updated from {}\n".format( assetToDownload.browser_download_url ) )

# Create output variables for use in the rest of the workflow

if args.setOutputs :
	print( "::set-output name=title::Update from {}".format( latestRelease.title ) )
	print( "::set-output name=body::Using documentation from {}".format( assetToDownload.browser_download_url ) )
