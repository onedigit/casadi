 /*
 *    This file is part of CasADi.
 *
 *    CasADi -- A symbolic framework for dynamic optimization.
 *    Copyright (C) 2010-2014 Joel Andersson, Joris Gillis, Moritz Diehl,
 *                            K.U. Leuven. All rights reserved.
 *    Copyright (C) 2011-2014 Greg Horn
 *
 *    CasADi is free software; you can redistribute it and/or
 *    modify it under the terms of the GNU Lesser General Public
 *    License as published by the Free Software Foundation; either
 *    version 3 of the License, or (at your option) any later version.
 *
 *    CasADi is distributed in the hope that it will be useful,
 *    but WITHOUT ANY WARRANTY; without even the implied warranty of
 *    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 *    Lesser General Public License for more details.
 *
 *    You should have received a copy of the GNU Lesser General Public
 *    License along with CasADi; if not, write to the Free Software
 *    Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA
 *
 */


#include "conic_activeset.hpp"
#include "casadi/core/nlpsol.hpp"

using namespace std;
namespace casadi {

  extern "C"
  int CASADI_CONIC_ACTIVESET_EXPORT
  casadi_register_conic_activeset(Conic::Plugin* plugin) {
    plugin->creator = ConicActiveSet::creator;
    plugin->name = "activeset";
    plugin->doc = ConicActiveSet::meta_doc.c_str();
    plugin->version = CASADI_VERSION;
    plugin->options = &ConicActiveSet::options_;
    return 0;
  }

  extern "C"
  void CASADI_CONIC_ACTIVESET_EXPORT casadi_load_conic_activeset() {
    Conic::registerPlugin(casadi_register_conic_activeset);
  }

  ConicActiveSet::ConicActiveSet(const std::string& name, const std::map<std::string, Sparsity> &st)
    : Conic(name, st) {
  }

  ConicActiveSet::~ConicActiveSet() {
    clear_mem();
  }

  Options ConicActiveSet::options_
  = {{&Conic::options_},
     {{"max_iter",
       {OT_INT,
        "Maximum number of iterations [1000]."}},
      {"pr_tol",
       {OT_DOUBLE,
        "Primal tolerance [1e-8]."}},
      {"du_tol",
       {OT_DOUBLE,
        "Dual tolerance [1e-8]."}}
     }
  };

  void ConicActiveSet::init(const Dict& opts) {
    // Initialize the base classes
    Conic::init(opts);

    // Default options
    max_iter_ = 1000;
    pr_tol_ = 1e-8;
    du_tol_ = 1e-8;

    // Read user options
    for (auto&& op : opts) {
      if (op.first=="max_iter") {
        max_iter_ = op.second;
      } else if (op.first=="pr_tol") {
        pr_tol_ = op.second;
      } else if (op.first=="du_tol") {
        du_tol_ = op.second;
      }
    }

    // Assemble KKT system sparsity
    kkt_ = Sparsity::kkt(H_, A_, false);

    // Transpose of the Jacobian
    AT_ = A_.T();

    // KKT with diagonal
    kktd_ = kkt_ + Sparsity::diag(nx_ + na_);

    // Symbolic QR factorization
    kktd_.qr_sparse(sp_v_, sp_r_, prinv_, pc_);

    // Allocate memory
    alloc_w(kkt_.nnz(), true); // kkt
    alloc_w(kktd_.nnz(), true); // kktd
    alloc_w(nx_, true); // xk
    alloc_w(na_, true); // gk
    alloc_w(nx_, true); // lam_xk
    alloc_w(na_, true); // lam_ak
    alloc_w(A_.nnz()); // trans(A)
    alloc_iw(nx_ + na_); // casadi_trans, tau type
    alloc_w(nx_ + na_); // casadi_project, [alpha_x, -lambda_g], [lambda_x, alpha_g], tau memory
    alloc_w(nx_, true); // alpha_x
    alloc_w(na_, true); // alpha_a
    alloc_w(nx_+na_, true); // step
    alloc_w(nx_, true); // dlam_x
    alloc_w(na_, true); // dg

    // Memory for numerical solution
    alloc_w(sp_v_.nnz(), true); // v
    alloc_w(sp_r_.nnz(), true); // r
    alloc_w(nx_+na_, true); // beta
    alloc_w(2*na_+2*nx_); // casadi_qr

    // Print summary
    print("-------------------------------------------\n");
    print("This is casadi::ConicActiveSet.\n");
    print("Number of variables:                       %9d\n", nx_);
    print("Number of constraints:                     %9d\n", na_);
    print("Work in progress!\n");
  }

  template<typename T1>
  void casadi_set_sub(const T1* y, T1* x, const casadi_int* sp_x,
                      casadi_int rbeg, casadi_int rend,
                      casadi_int cbeg, casadi_int cend) {
    // Local variables
    casadi_int r, c, k;
    // Get sparsities
    casadi_int nrow=sp_x[0], ncol=sp_x[1];
    const casadi_int *colind=sp_x+2, *row=sp_x+2+ncol+1;
    // Set elements in subblock
    for (c=cbeg; c<cend; ++c) {
      for (k=colind[c]; k<colind[c+1] && (r=row[k])<rend; ++k) {
        if (r>=rbeg) x[k] = *y++;
      }
    }
  }

  template<typename T1>
  void casadi_fill_sub(T1 y, T1* x, const casadi_int* sp_x,
                      casadi_int rbeg, casadi_int rend,
                      casadi_int cbeg, casadi_int cend) {
    // Local variables
    casadi_int r, c, k;
    // Get sparsities
    casadi_int nrow=sp_x[0], ncol=sp_x[1];
    const casadi_int *colind=sp_x+2, *row=sp_x+2+ncol+1;
    // Set elements in subblock
    for (c=cbeg; c<cend; ++c) {
      for (k=colind[c]; k<colind[c+1] && (r=row[k])<rend; ++k) {
        if (r>=rbeg) x[k] = y;
      }
    }
  }

  template<typename T1>
  void casadi_row_scal(T1* x, const casadi_int* sp_x, const T1* d) {
    // Local variables
    casadi_int c, k;
    // Get sparsities
    casadi_int ncol=sp_x[1];
    const casadi_int *colind=sp_x+2, *row=sp_x+2+ncol+1;
    // Scale entries
    for (c=0; c<ncol; ++c) {
      for (k=colind[c]; k<colind[c+1]; ++k) {
        x[k] *= d[row[k]];
      }
    }
  }

  void print_vector(const double* x, casadi_int n) {
    cout << vector<double>(x, x+n) << endl;
  }

  void print_matrix(const double* x, const casadi_int* sp_x) {
    Sparsity sp = Sparsity::compressed(sp_x);
    vector<double> nz(x, x+sp.nnz());
    DM(sp, nz).print_dense(cout, false);
    cout << endl;
  }

  template<typename T1>
  void casadi_col_scal(T1* x, const casadi_int* sp_x, const T1* d) {
    // Local variables
    casadi_int c, k;
    // Get sparsities
    casadi_int ncol=sp_x[1];
    const casadi_int *colind=sp_x+2;
    // Scale entries
    for (c=0; c<ncol; ++c) {
      for (k=colind[c]; k<colind[c+1]; ++k) {
        x[k] *= d[c];
      }
    }
  }

  template<typename T1>
  void casadi_add_diag(T1* x, const casadi_int* sp_x, const T1* d) {
    // Local variables
    casadi_int c, k;
    // Get sparsities
    casadi_int ncol=sp_x[1];
    const casadi_int *colind=sp_x+2, *row=sp_x+2+ncol+1;
    // Add to diagonal entry
    for (c=0; c<ncol; ++c) {
      for (k=colind[c]; k<colind[c+1]; ++k) {
        if (row[k]==c) {
          x[k] += d[c];
          break;
        }
      }
    }
  }

  int ConicActiveSet::init_mem(void* mem) const {
    auto m = static_cast<ConicActiveSetMemory*>(mem);
    return 0;
  }

  int ConicActiveSet::
  eval(const double** arg, double** res, casadi_int* iw, double* w, void* mem) const {
    auto m = static_cast<ConicActiveSetMemory*>(mem);

    // Statistics
    for (auto&& s : m->fstats) s.second.reset();

    if (inputs_check_) {
      check_inputs(arg[CONIC_LBX], arg[CONIC_UBX], arg[CONIC_LBA], arg[CONIC_UBA]);
    }

    // Local variables
    casadi_int i;
    double lb, ub, trial, fk;
    // Get input pointers
    const double *h, *g, *a, *lba, *uba, *lbx, *ubx, *x0, *lam_x0, *lam_a0;
    h = arg[CONIC_H];
    g = arg[CONIC_G];
    a = arg[CONIC_A];
    lba = arg[CONIC_LBA];
    uba = arg[CONIC_UBA];
    lbx = arg[CONIC_LBX];
    ubx = arg[CONIC_UBX];
    x0 = arg[CONIC_X0];
    lam_x0 = arg[CONIC_LAM_X0];
    lam_a0 = arg[CONIC_LAM_A0];

    // Get output pointers
    double *x, *f, *lam_a, *lam_x;
    x = res[CONIC_X];
    f = res[CONIC_COST];
    lam_a = res[CONIC_LAM_A];
    lam_x = res[CONIC_LAM_X];

    // Work vectors
    double *kkt, *kktd, *xk, *lam_xk, *lam_ak, *v, *r, *beta,
           *alpha_x, *alpha_a, *gk, *step, *dlam_x, *dg;
    kkt = w; w += kkt_.nnz();
    kktd = w; w += kktd_.nnz();
    xk = w; w += nx_;
    gk = w; w += na_;
    lam_xk = w; w += nx_;
    lam_ak = w; w += na_;
    alpha_x = w; w += nx_;
    alpha_a = w; w += na_;
    step = w; w += nx_+na_;
    dlam_x = w; w += nx_;
    dg = w; w += na_;
    v = w; w += sp_v_.nnz();
    r = w; w += sp_r_.nnz();
    beta = w; w += nx_+na_;

    // Pass initial guess
    casadi_copy(x0, nx_, xk);
    casadi_copy(lam_x0, nx_, lam_xk);
    casadi_copy(lam_a0, na_, lam_ak);

    // Copy A' to w
    casadi_trans(a, A_, w, AT_, iw);

    // Assemble the KKT matrix
    casadi_set_sub(h, kkt, kkt_, 0, nx_, 0, nx_); // h
    casadi_set_sub(a, kkt, kkt_, nx_, nx_+na_, 0, nx_); // a
    casadi_set_sub(w, kkt, kkt_, 0, nx_, nx_, nx_+na_); // a'

    // Calculate g
    casadi_fill(gk, na_, 0.);
    casadi_mv(a, A_, xk, gk, 0);

    // Smallest strictly positive number
    const double DMIN = std::numeric_limits<double>::min();

    // Determine initial active set for simple bounds
    for (i=0; i<nx_; ++i) {
      lb = lbx ? lbx[i] : 0.;
      ub = ubx ? ubx[i] : 0.;
      if (lb!=ub) {
        // All inequality constraints are inactive
        lam_xk[i] = 0;
      } else if (xk[i]<=lb) {
        // Lower bound active (including satisfied bounds)
        lam_xk[i] = fmin(lam_xk[i], -DMIN);
      } else {
        // Upper bound active (excluding satisfied bounds)
        lam_xk[i] = fmax(lam_xk[i],  DMIN);
      }
    }

    // Determine initial active set for simple bounds
    for (i=0; i<na_; ++i) {
      lb = lba ? lba[i] : 0.;
      ub = uba ? uba[i] : 0.;
      if (lb!=ub) {
        // All inequality constraints are inactive
        lam_ak[i] = 0;
      } else if (gk[i]<=ub) {
        // Lower bound active (including satisfied bounds)
        lam_ak[i] = fmin(lam_ak[i], -DMIN);
      } else {
        // Upper bound active (excluding satisfied bounds)
        lam_ak[i] = fmax(lam_ak[i], DMIN);
      }
    }

    // kktd sparsity
    const casadi_int* kkt_colind = kktd_.colind();
    const casadi_int* kkt_row = kktd_.row();

    // A sparsity
    const casadi_int* a_colind = A_.colind();
    const casadi_int* a_row = A_.row();

    // No change so far
    bool new_active_set = true;

    // QP iterations
    casadi_int iter = 0;
    while (true) {
      // Debugging
      if (verbose_) {
        print("Current xk = \n");
        print_vector(xk, nx_);
        print("Current gk = \n");
        print_vector(gk, na_);
        print("Current lam_xk = \n");
        print_vector(lam_xk, nx_);
        print("Current lam_ak = \n");
        print_vector(lam_ak, na_);
      }

      // Recalculate g
      casadi_fill(gk, na_, 0.);
      casadi_mv(a, A_, xk, gk, 0);

      // Evaluate gradient of the Lagrangian and constraint functions
      casadi_copy(g, nx_, step);
      casadi_mv(h, H_, xk, step, 0); // gradient of the objective
      casadi_mv(a, A_, lam_ak, step, 1); // gradient of the Lagrangian

      // Recalculate lam_xk, without changing the sign
      for (i=0; i<nx_; ++i) {
        if (lam_xk[i]>0) {
          lam_xk[i] = fmax(-step[i], DMIN);
        } else if (lam_xk[i]<0) {
          lam_xk[i] = fmin(-step[i], -DMIN);
        }
      }

      // Calculate cost
      fk = casadi_bilin(h, H_, xk, xk)/2. + casadi_dot(nx_, xk, g);

      // Look for largest x bound violation
      double maxpr = 0.;
      casadi_int imaxpr;
      for (i=0; i<nx_; ++i) {
        lb = lbx ? lbx[i] : 0.;
        ub = ubx ? ubx[i] : 0.;
        if (xk[i] > ub+maxpr) {
          maxpr = xk[i]-ub;
          imaxpr = i;
        } else if (xk[i] < lb-maxpr) {
          maxpr = lb-xk[i];
          imaxpr = i;
        }
      }

      // Look for largest a bound violation
      for (i=0; i<na_; ++i) {
        lb = lba ? lba[i] : 0.;
        ub = uba ? uba[i] : 0.;
        if (gk[i] > ub+maxpr) {
          maxpr = gk[i]-ub;
          imaxpr = nx_+i;
        } else if (gk[i] < lb-maxpr) {
          maxpr = lb-gk[i];
          imaxpr = nx_+i;
        }
      }

      // Calculate dual infeasibility
      double maxdu = 0.;
      casadi_int imaxdu;
      for (i=0; i<nx_; ++i) {
        double maxdu_trial = fabs(step[i]+lam_xk[i]);
        if (maxdu_trial>maxdu) {
          maxdu = maxdu_trial;
          imaxdu = i;
        }
      }

      // Found optimal value?
      bool pr_feasible = maxpr<pr_tol_;
      bool du_feasible = maxdu<du_tol_;
      bool success = pr_feasible && du_feasible;

      // Feasibility restoration?
      if (!success && !new_active_set) {
        if (!pr_feasible) {
          // Restore primal feasibility
          if (imaxpr<nx_) {
            i = imaxpr;
            // Add x constraint
            lb = lbx ? lbx[i] : 0.;
            ub = ubx ? ubx[i] : 0.;
            if (lam_xk[i]!=0.) {
              // If already active constraint, terminate
              casadi_warning("Failed to restore primal feasibility");
              break;
            } else {
              // Add constraint to active set
              if (xk[i] < lb) {
                lam_xk[i] = fmin(-w[i], -DMIN);
                new_active_set = true;
                continue;
              } else if (xk[i] > ub) {
                lam_xk[i] = fmax(-w[i],  DMIN);
                new_active_set = true;
                continue;
              } else {
                casadi_warning("Failed to restore primal feasibility");
                break; // can it happen?
              }
            }
          } else {
            i = imaxpr-nx_;
            // Add a constraint
            lb = lba ? lba[i] : 0.;
            ub = uba ? uba[i] : 0.;
            // If already active constraint, terminate
            if (lam_ak[i]!=0.) {
              casadi_warning("Failed to restore primal feasibility");
              break;
            } else {
              // Add constraint to active set
              if (gk[i] < lb) {
                lam_ak[i] = -DMIN;
                new_active_set = true;
                continue;
              } else if (gk[i] > ub) {
                lam_ak[i] = DMIN;
                new_active_set = true;
                continue;
              } else {
                casadi_warning("Failed to restore primal feasibility");
                break; // can it happen?
              }
            }
          }
        } else {
          // We're feasible but not optimal, let's remove a redundant constraint
          double best_a = 0.;
          casadi_int ibest_a;

          // If calculated residual is positive, we need a negative lhs
          bool negative_lhs = step[i]+lam_xk[i]>0.;

          // Check redundancy in x bounds with the right sign
          bool negative_lambda = negative_lhs; // coefficient is 1.
          i=imaxdu;
          if (lam_xk[i]!=0. && negative_lambda==(lam_xk[i]>0.)) {
            best_a = 1.;
            ibest_a = i;
          }

          // Check redundancy in g bounds matching imaxdu with the right sign
          for (casadi_int k=a_colind[imaxdu]; k<a_colind[imaxdu+1]; ++k) {
            i = a_row[k];
            if (lam_ak[i]!=0. && fabs(a[k])>best_a) {
              negative_lambda = negative_lhs==a[k]>0.;
              if (negative_lambda==(lam_ak[i]>0.)) {
                best_a = fabs(a[k]);
                ibest_a = nx_+i;
              }
            }
          }

          // Remove redundant constraint, if any
          if (best_a>0.) {
            if (ibest_a<nx_) {
              lam_xk[ibest_a] = 0.;
            } else {
              lam_ak[ibest_a-nx_] = 0.;
            }
            new_active_set = true;
            continue;
          }
        }

        casadi_warning("Failed to restore dual feasibility");
        break;
      }

      // Print iteration progress:
      print("Iteration %d: fk=%g, |pr|=%g, |du|=%g\n",
            iter, fk, maxpr, maxdu);

      // Terminate successfully?
      if (success || !new_active_set)  {
        if (!pr_feasible) casadi_warning("Primal tolerance not met");
        if (!du_feasible) casadi_warning("Dual tolerance not met");
        break;
      }

      // Start new iteration
      if (++iter==max_iter_) {
        casadi_warning("Maximum number of iterations reached");
        break;
      }

      // No change so far
      new_active_set = false;

      // Calculate KKT residual: Correct for active simple bounds
      for (i=0; i<nx_; ++i) {
        if (lam_xk[i]!=0.) {
          step[i] = xk[i];
          if (lbx && lam_xk[i]<0) step[i] -= lbx[i];
          if (ubx && lam_xk[i]>0) step[i] -= ubx[i];
        }
      }

      // Calculate KKT residual: Correct for inactive constraints
      casadi_copy(gk, na_, step + nx_); // constraint evaluation
      for (i=0; i<na_; ++i) {
        if (lam_ak[i]==0) {
          step[nx_+i] = 0.; // -lam_ak[i]
        } else if (lba && lam_ak[i]<0) {
          step[nx_+i] -= lba[i];
        } else if (uba && lam_ak[i]>0) {
          step[nx_+i] -= uba[i];
        }
      }

      if (verbose_) {
        print("KKT residual = \n");
        print_vector(step, nx_ + na_);
      }

      // Copy kkt to kktd
      casadi_project(kkt, kkt_, kktd, kktd_, w);

      // Loop over kktd entries (left two blocks of the transposed KKT)
      for (casadi_int c=0; c<nx_; ++c) {
        if (lam_xk[c]!=0) {
          // Zero out column, set diagonal entry to 1
          for (casadi_int k=kkt_colind[c]; k<kkt_colind[c+1]; ++k) {
            kktd[k] = kkt_row[k]==c ? 1. : 0.;
          }
        }
      }

      // Loop over kktd entries (right two blocks of the transposed KKT)
      for (casadi_int c=0; c<na_; ++c) {
        if (lam_ak[c]==0) {
          // Zero out column, set diagonal entry to -1
          for (casadi_int k=kkt_colind[nx_+c]; k<kkt_colind[nx_+c+1]; ++k) {
            kktd[k] = kkt_row[k]==nx_+c ? -1. : 0.;
          }
        }
      }

      // QR factorization
      casadi_qr(kktd_, kktd, w, sp_v_, v, sp_r_, r, beta, get_ptr(prinv_), get_ptr(pc_));

      // Solve to get primal-dual step
      casadi_scal(nx_+na_, -1., step);
      casadi_qr_solve(step, 1, 1, sp_v_, v, sp_r_, r, beta,
                      get_ptr(prinv_), get_ptr(pc_), w);

      // Remove NaNs
      for (i=0; i<nx_+na_; ++i) if (isnan(step[i])) step[i]=0.;

      // Calculate change in Lagrangian gradient
      casadi_fill(dlam_x, nx_, 0.);
      casadi_mv(h, H_, step, dlam_x, 0); // gradient of the objective
      casadi_mv(a, A_, step+nx_, dlam_x, 1); // gradient of the Lagrangian

      // Step in lambda_x
      casadi_scal(nx_, -1., dlam_x);

      // Step in g
      casadi_fill(dg, na_, 0.);
      casadi_mv(a, A_, step, dg, 0);

      if (verbose_) {
        print("dx = \n");
        print_vector(step, nx_);
        print("dg = \n");
        print_vector(dg, na_);
        print("dlam_x = \n");
        print_vector(dlam_x, nx_);
        print("dlam_g = \n");
        print_vector(step+nx_, na_);
      }

      // Get maximum step size
      double tau = 1.;

      // Remember best tau for each constraint
      casadi_fill(w, nx_+na_, -1.);

      // iw will be used to mark the new sign:
      // -1: Lower bound became active
      //  0: Bound became inactive
      //  1: Upper bound became active

      // Loop over primal variables
      for (i=0; i<nx_; ++i) {
        lb = lbx ? lbx[i] : 0.;
        ub = ubx ? ubx[i] : 0.;
        if (lam_xk[i]==0.) {
          // Trial step
          trial=xk[i] + tau*step[i];

          // Constraint is inactive, check for primal blocking constraints
          if (trial<=lb && xk[i]>lb) {
            // Lower bound hit
            tau = (lb-xk[i])/step[i];
            w[i] = tau;
            iw[i] = -1;
          } else if (trial>=ub && xk[i]<ub) {
            // Upper bound hit
            tau = (ub-xk[i])/step[i];
            w[i] = tau;
            iw[i] = 1;
          }
        } else {
          trial = lam_xk[i] + tau*dlam_x[i];
          // Constraint is active, check for dual blocking constraints
          if ((lam_xk[i]<0. && trial>=0) || (lam_xk[i]>0. && trial<=0)) {
            // Sign changes
            tau = -lam_xk[i]/dlam_x[i];
            w[i] = tau;
            iw[i] = 0;
          }
        }
      }

      // Loop over constraints
      for (i=0; i<na_; ++i) {
        lb = lba ? lba[i] : 0.;
        ub = uba ? uba[i] : 0.;
        if (lam_ak[i]==0.) {
          // Trial step
          trial=gk[i] + tau*dg[i];
          // Constraint is inactive, check for primal blocking constraints
          if (trial<lb && gk[i]>=lb) {
            // Lower bound hit
            tau = (lb-gk[i])/dg[i];
            w[nx_+i] = tau;
            iw[nx_+i] = -1;
          } else if (trial>ub && gk[i]<=ub) {
            // Upper bound hit
            tau = (ub-gk[i])/dg[i];
            w[nx_+i] = tau;
            iw[nx_+i] = 1;
          }
        } else {
          trial = lam_ak[i] + tau*step[nx_+i];
          // Constraint is active, check for sign changes
          if (lam_ak[i]!=0 && ((lam_ak[i]>0)!=(trial>0))) {
            // Sign changes
            tau = -lam_ak[i]/step[nx_+i];
            w[nx_+i] = tau;
            iw[nx_+i] = 0;
          }
        }
      }

      if (verbose_) {
        print("tau = %g\n", tau);
      }

      // If tau==0, no step to take
      if (tau==0.) continue;

      // Take primal step
      casadi_axpy(nx_, tau, step, xk);

      // Update lam_ak carefully
      for (i=0; i<na_; ++i) {
        // Get the current sign
        casadi_int s = lam_ak[i]>0. ? 1 : lam_ak[i]<0. ? -1 : 0;
        // Account for sign changes
        if (w[nx_+i]==tau) {
          new_active_set = true;
          s = iw[nx_+i];
        }
        // Take step
        lam_ak[i] += tau*step[nx_+i];
        // Ensure correct sign
        switch (s) {
          case -1: lam_ak[i] = fmin(lam_ak[i], -DMIN); break;
          case  1: lam_ak[i] = fmax(lam_ak[i],  DMIN); break;
          case  0: lam_ak[i] = 0.; break;
        }
      }

      // Update sign for lam_xk
      for (i=0; i<nx_; ++i) {
        if (w[i]==tau) {
          new_active_set = true;
          lam_xk[i] = iw[i]; // only sign, value will be calculated later
        }
      }
    }

    // Calculate optimal cost
    if (f) *f = fk;

    // Get solution
    casadi_copy(xk, nx_, x);
    casadi_copy(lam_xk, nx_, lam_x);
    casadi_copy(lam_ak, na_, lam_a);

    return 0;
  }

} // namespace casadi