/*
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements. See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership. The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License. You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing,
 * software distributed under the License is distributed on an
 * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 * KIND, either express or implied. See the License for the
 * specific language governing permissions and limitations
 * under the License.
 */

#ifndef _THRIFT_CONCURRENCY_GUARD_H_
#define _THRIFT_CONCURRENCY_GUARD_H_ 1

#include <boost/shared_ptr.hpp>

namespace apache { namespace thrift { namespace concurrency {

template<typename T>
class GuardBase {
 public:
  GuardBase(const T& value) : mutex_(value) {
    mutex_.lock();
  }
  ~GuardBase() {
    mutex_.unlock();
  }

 private:
  const T& mutex_;
};

template <typename T>
class RWGuardBase {
  public:
    RWGuardBase(const T& value, bool write = 0) : mutex_(value) {
      if (write) {
        mutex_.acquireWrite();
      } else {
        mutex_.acquireRead();
      }
    }
    ~RWGuardBase() {
      mutex_.release();
    }
  private:
    const T& mutex_;
};

}}} // apache::thrift::concurrency

#endif // #ifndef _THRIFT_CONCURRENCY_GUARD_H_
