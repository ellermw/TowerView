            {groupedSessions.map(({ serverType, servers }) => {
              const allServerTypeSessions = servers.flatMap(server => server.sessions)
              const serverTypeStats = calculateStats(allServerTypeSessions)

              return (
                <Disclosure key={serverType} defaultOpen={true}>
                  {({ open }) => (
                    <div className="card">
                      <Disclosure.Button className="w-full">
                        <div className="card-body">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center space-x-3">
                              {open ? (
                                <ChevronDownIcon className="h-4 w-4 text-slate-500" />
                              ) : (
                                <ChevronRightIcon className="h-4 w-4 text-slate-500" />
                              )}
                              <span className="text-xl">{getServerTypeIcon(serverType)}</span>
                              <h3 className="text-lg font-bold text-slate-900 dark:text-white">
                                {getServerTypeName(serverType)}
                              </h3>
                            </div>
                            <div className="flex items-center space-x-4 text-sm">
                              <div className="flex items-center">
                                <PlayIcon className="h-3 w-3 text-slate-400 mr-1" />
                                <span className="font-medium text-slate-900 dark:text-white">
                                  {serverTypeStats.totalStreams}
                                </span>
                              </div>
                              <div className="flex items-center">
                                <SignalIcon className="h-3 w-3 text-orange-500 mr-1" />
                                <span className="font-medium text-slate-900 dark:text-white">
                                  {serverTypeStats.transcodes}
                                </span>
                              </div>
                            </div>
                          </div>
                        </div>
                      </Disclosure.Button>

                      <Transition
                        show={open}
                        enter="transition duration-150 ease-out"
                        enterFrom="transform scale-95 opacity-0"
                        enterTo="transform scale-100 opacity-100"
                        leave="transition duration-75 ease-out"
                        leaveFrom="transform scale-100 opacity-100"
                        leaveTo="transform scale-95 opacity-0"
                      >
                        <Disclosure.Panel>
                          <div className="px-6 pb-6 space-y-3">
                            {servers.map(({ serverName, sessions: serverSessions }) => {
                              const serverStats = calculateStats(serverSessions)

                              return (
                                <Disclosure key={`${serverType}-${serverName}`} defaultOpen={true}>
                                  {({ open: serverOpen }) => (
                                    <div className="border border-slate-200 dark:border-slate-700 rounded-lg">
                                      <Disclosure.Button className="w-full">
                                        <div className="p-3 bg-slate-50 dark:bg-slate-800/50 rounded-t-lg">
                                          <div className="flex items-center justify-between">
                                            <div className="flex items-center space-x-2">
                                              {serverOpen ? (
                                                <ChevronDownIcon className="h-3 w-3 text-slate-500" />
                                              ) : (
                                                <ChevronRightIcon className="h-3 w-3 text-slate-500" />
                                              )}
                                              <h4 className={`text-sm font-semibold ${getServerTypeColor(serverType)}`}>
                                                {serverName}
                                              </h4>
                                            </div>
                                            <div className="flex items-center space-x-3 text-xs">
                                              <span className="font-medium">{serverStats.totalStreams} streams</span>
                                              <span className="font-medium text-orange-500">{serverStats.transcodes} transcoding</span>
                                            </div>
                                          </div>
                                        </div>
                                      </Disclosure.Button>

                                      <Transition
                                        show={serverOpen}
                                        enter="transition duration-100 ease-out"
                                        enterFrom="transform scale-95 opacity-0"
                                        enterTo="transform scale-100 opacity-100"
                                        leave="transition duration-75 ease-out"
                                        leaveFrom="transform scale-100 opacity-100"
                                        leaveTo="transform scale-95 opacity-0"
                                      >
                                        <Disclosure.Panel>
                                          <div className="p-3 grid gap-3 md:grid-cols-2 lg:grid-cols-3">
                                            {serverSessions.map((session) => (
                                              <div key={session.session_id} className="border border-slate-100 dark:border-slate-700 rounded p-3">
                                                <div className="flex items-start justify-between mb-2">
                                                  <div>
                                                    <h5 className="font-medium text-slate-900 dark:text-white text-xs mb-1">
                                                      {session.title || session.full_title || 'Unknown Media'}
                                                    </h5>
                                                    {session.grandparent_title && (
                                                      <p className="text-xs text-slate-600 dark:text-slate-400">
                                                        {session.grandparent_title}
                                                        {session.parent_title && ` - ${session.parent_title}`}
                                                      </p>
                                                    )}
                                                  </div>
                                                  <button
                                                    onClick={() => terminateSessionMutation.mutate({
                                                      serverId: session.server_id!,
                                                      sessionId: session.session_id
                                                    })}
                                                    disabled={terminateSessionMutation.isLoading}
                                                    className="p-1 text-red-500 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-900/20 rounded transition-colors"
                                                    title="Terminate Session"
                                                  >
                                                    <XMarkIcon className="w-3 h-3" />
                                                  </button>
                                                </div>

                                                <div className="space-y-1 text-xs text-slate-600 dark:text-slate-400">
                                                  <div className="flex justify-between">
                                                    <span>User:</span>
                                                    <span className="font-medium text-slate-900 dark:text-white">{session.username || 'Unknown'}</span>
                                                  </div>
                                                  <div className="flex justify-between">
                                                    <span>State:</span>
                                                    <span className="flex items-center gap-1">
                                                      {getStateIcon(session.state)}
                                                      <span className="capitalize font-medium text-slate-900 dark:text-white">{session.state}</span>
                                                    </span>
                                                  </div>
                                                  <div className="flex justify-between">
                                                    <span>Quality:</span>
                                                    <span className="font-medium text-slate-900 dark:text-white">
                                                      {session.video_decision === 'transcode' ? (
                                                        <span className="text-orange-500">Transcoding</span>
                                                      ) : (
                                                        <span className="text-green-500">Direct</span>
                                                      )}
                                                    </span>
                                                  </div>
                                                </div>

                                                {/* Progress Bar */}
                                                <div className="mt-2">
                                                  <div className="flex justify-between text-xs text-slate-600 dark:text-slate-400 mb-1">
                                                    <span>{formatTime(session.progress_ms)}</span>
                                                    <span>{session.progress_percent.toFixed(0)}%</span>
                                                  </div>
                                                  <div className="w-full bg-slate-200 dark:bg-slate-700 rounded-full h-1">
                                                    <div
                                                      className={`h-1 rounded-full transition-all duration-300 ${getProgressBarColor(session.state)}`}
                                                      style={{ width: `${Math.min(100, Math.max(0, session.progress_percent))}%` }}
                                                    />
                                                  </div>
                                                </div>
                                              </div>
                                            ))}
                                          </div>
                                        </Disclosure.Panel>
                                      </Transition>
                                    </div>
                                  )}
                                </Disclosure>
                              )
                            })}
                          </div>
                        </Disclosure.Panel>
                      </Transition>
                    </div>
                  )}
                </Disclosure>
              )
            })}